#!/usr/bin/env python3
"""Read-only AWS waste scan with a before/after check. Standard library only.

  waste.py demo                                   made-up data, no AWS account
  waste.py scan --region us-east-1 --out before.json
  waste.py compare before.json after.json
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

# The only AWS operations this script can run. All of them read.
ALLOWED = {
    ("sts", "get-caller-identity"),
    ("ec2", "describe-volumes"),
    ("ec2", "describe-addresses"),
    ("ec2", "describe-instances"),
    ("ec2", "describe-snapshots"),
    ("logs", "describe-log-groups"),
}


class AwsError(Exception):
    pass


def aws(service, operation, region, extra=()):
    if (service, operation) not in ALLOWED:
        raise ValueError(f"blocked: {service} {operation} is not on the read-only list")
    cmd = ["aws", service, operation, "--region", region, "--output", "json", *extra]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                             env={**os.environ, "AWS_PAGER": ""})
    except FileNotFoundError:
        raise AwsError("the AWS CLI (`aws`) is not installed")
    except subprocess.TimeoutExpired:
        raise AwsError(f"{service} {operation} timed out")
    if out.returncode != 0:
        raise AwsError(out.stderr.strip() or f"{service} {operation} failed")
    return json.loads(out.stdout)


def finding(check, region, resource, evidence, verify):
    return {"id": f"{check}:{region}:{resource}", "check": check, "region": region,
            "resource": resource, "evidence": evidence, "verify": verify}


def unattached_volumes(run, region, opts):
    data = run("ec2", "describe-volumes", region)
    return [finding("unattached-volume", region, v["VolumeId"],
                    f"{v['Size']} GiB {v['VolumeType']} volume in state 'available'",
                    f"aws ec2 describe-volumes --region {region} --volume-ids {v['VolumeId']}")
            for v in data["Volumes"] if v["State"] == "available"]


def gp2_volumes(run, region, opts):
    data = run("ec2", "describe-volumes", region)
    return [finding("gp2-volume", region, v["VolumeId"],
                    f"{v['Size']} GiB gp2 volume; compare gp3 price and performance",
                    f"aws ec2 describe-volumes --region {region} --volume-ids {v['VolumeId']}")
            for v in data["Volumes"] if v["VolumeType"] == "gp2"]


def idle_addresses(run, region, opts):
    data = run("ec2", "describe-addresses", region)
    out = []
    for a in data["Addresses"]:
        if a.get("AssociationId"):
            continue
        key = a.get("AllocationId") or a["PublicIp"]
        out.append(finding("idle-elastic-ip", region, key,
                           "Elastic IP with no association",
                           f"aws ec2 describe-addresses --region {region} --public-ips {a['PublicIp']}"))
    return out


def stopped_instances(run, region, opts):
    data = run("ec2", "describe-instances", region)
    out = []
    for reservation in data["Reservations"]:
        for i in reservation["Instances"]:
            volumes = [m["Ebs"]["VolumeId"] for m in i.get("BlockDeviceMappings", []) if "Ebs" in m]
            if i["State"]["Name"] == "stopped" and volumes:
                out.append(finding("stopped-instance-storage", region, i["InstanceId"],
                                   f"stopped instance still holds {len(volumes)} EBS volume(s): {', '.join(volumes)}",
                                   f"aws ec2 describe-instances --region {region} --instance-ids {i['InstanceId']}"))
    return out


def old_snapshots(run, region, opts):
    data = run("ec2", "describe-snapshots", region, ("--owner-ids", "self"))
    cutoff = opts["now"] - dt.timedelta(days=opts["snapshot_days"])
    out = []
    for s in data["Snapshots"]:
        started = dt.datetime.fromisoformat(s["StartTime"].replace("Z", "+00:00"))
        if started < cutoff:
            out.append(finding("old-snapshot", region, s["SnapshotId"],
                               f"started {started.date()}, source volume size {s['VolumeSize']} GiB; "
                               "check AMIs and backup rules before deleting",
                               f"aws ec2 describe-snapshots --region {region} --snapshot-ids {s['SnapshotId']}"))
    return out


def endless_logs(run, region, opts):
    data = run("logs", "describe-log-groups", region)
    return [finding("log-group-no-retention", region, g["logGroupName"],
                    f"no retention policy, {g.get('storedBytes', 0) / 1024 ** 3:.2f} GiB stored",
                    f"aws logs describe-log-groups --region {region} "
                    f"--log-group-name-prefix '{g['logGroupName']}'")
            for g in data["logGroups"] if "retentionInDays" not in g]


CHECKS = {
    "unattached-volume": unattached_volumes,
    "gp2-volume": gp2_volumes,
    "idle-elastic-ip": idle_addresses,
    "stopped-instance-storage": stopped_instances,
    "old-snapshot": old_snapshots,
    "log-group-no-retention": endless_logs,
}


def scan(regions, snapshot_days=365, run=aws, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    account = run("sts", "get-caller-identity", regions[0])["Account"]
    opts = {"now": now, "snapshot_days": snapshot_days}
    findings, completed, errors = [], [], []
    for region in regions:
        for name, check in CHECKS.items():
            try:
                findings.extend(check(run, region, opts))
                completed.append(f"{name}:{region}")
            except AwsError as e:
                errors.append({"check": name, "region": region, "error": str(e)})
    return {"account": account, "scanned_at": now.isoformat(timespec="seconds"),
            "snapshot_days": snapshot_days, "completed": completed,
            "errors": errors, "findings": findings}


def compare(before, after):
    """Sort findings into resolved, still open, new, and unknown.

    A finding counts as resolved only when the same check ran without error in
    the same region of the same account and no longer reports the resource.
    """
    if before["account"] != after["account"]:
        raise ValueError("the two scans are from different AWS accounts")
    if before["snapshot_days"] != after["snapshot_days"]:
        raise ValueError("the two scans used different --snapshot-days values")
    old = {f["id"]: f for f in before["findings"]}
    new = {f["id"]: f for f in after["findings"]}
    ran_before, ran_after = set(before["completed"]), set(after["completed"])
    result = {"resolved": [], "still_open": [], "new": [], "unknown": []}
    for key, f in old.items():
        if f"{f['check']}:{f['region']}" not in ran_after:
            result["unknown"].append(f)
        elif key in new:
            result["still_open"].append(new[key])
        else:
            result["resolved"].append(f)
    for key, f in new.items():
        if key not in old:
            # If the check did not run before, we cannot say the finding is new.
            bucket = "new" if f"{f['check']}:{f['region']}" in ran_before else "unknown"
            result[bucket].append(f)
    return result


def rows(findings):
    lines = ["| Check | Region | Resource | Evidence |", "|---|---|---|---|"]
    for f in sorted(findings, key=lambda f: f["id"]):
        lines.append(f"| {f['check']} | {f['region']} | `{f['resource']}` | {f['evidence']} |")
    return lines


def render_scan(report):
    lines = [f"# AWS waste scan, {report['scanned_at']}", "",
             f"{len(report['findings'])} findings. "
             f"{len(report['completed'])} checks ran, {len(report['errors'])} failed.", ""]
    if report["findings"]:
        lines += rows(report["findings"])
    if report["errors"]:
        lines += ["", "## Checks that failed (these resources were NOT checked)", ""]
        lines += [f"- {e['check']} in {e['region']}: {' '.join(e['error'].split())}" for e in report["errors"]]
    return "\n".join(lines) + "\n"


def render_compare(result):
    titles = {"resolved": "Resolved", "still_open": "Still open", "new": "New",
              "unknown": "Unknown (the check did not run in both scans)"}
    lines = ["# Before and after", "",
             ", ".join(f"{len(result[k])} {k.replace('_', ' ')}" for k in titles), ""]
    for key, title in titles.items():
        if result[key]:
            lines += [f"## {title}", "", *rows(result[key]), ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="scan one or more regions")
    s.add_argument("--region", action="append", required=True, help="repeat for more regions")
    s.add_argument("--snapshot-days", type=int, default=365)
    s.add_argument("--out", required=True, help="where to save the JSON report")
    c = sub.add_parser("compare", help="compare two saved scans")
    c.add_argument("before")
    c.add_argument("after")
    sub.add_parser("demo", help="before/after on made-up data, no AWS account needed")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            here = os.path.dirname(os.path.abspath(__file__))
            now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
            reports = []
            for name in ("demo-before.json", "demo-after.json"):
                with open(os.path.join(here, name)) as fh:
                    data = json.load(fh)
                reports.append(scan(["us-east-1"], run=lambda s, op, r, extra=(), d=data: d[op], now=now))
            print(render_compare(compare(*reports)))
            return 0
        if args.command == "scan":
            report = scan(args.region, args.snapshot_days)
            with open(args.out, "w") as fh:
                json.dump(report, fh, indent=2)
            print(render_scan(report))
            return 2 if report["errors"] else 0
        with open(args.before) as a, open(args.after) as b:
            result = compare(json.load(a), json.load(b))
        print(render_compare(result))
        return 2 if result["unknown"] else 0
    except (AwsError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
