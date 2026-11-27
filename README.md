# aws-waste-proof

**Find unused AWS resources. Clean them up. Prove they are gone.**

One read-only Python script. Scan, clean up, scan again, and see what changed:

```text
4 resolved, 2 still open, 1 new, 0 unknown

Resolved
  unattached-volume        vol-loose         500 GiB gp3 volume in state 'available'
  idle-elastic-ip          eipalloc-idle     Elastic IP with no association
Still open
  old-snapshot             snap-old          started 2023-03-01
New
  unattached-volume        vol-new           20 GiB gp3 volume in state 'available'
```

## Try it in 10 seconds (no AWS account)

```bash
git clone https://github.com/ravsau/aws-waste-proof && python3 aws-waste-proof/examples/demo.py
```

The demo uses made-up data. The output above is shortened.

## Run it on your account

You need Python 3.9 or later and a configured AWS CLI.

```bash
cd aws-waste-proof/skills/aws-waste-proof
python3 scripts/waste.py scan --region us-east-1 --out before.json
# clean up what you decide to clean up
python3 scripts/waste.py scan --region us-east-1 --out after.json
python3 scripts/waste.py compare before.json after.json
```

Or use it as a Claude Code skill: `/plugin marketplace add ravsau/aws-waste-proof`, then
`/plugin install aws-waste-proof@aws-waste-proof`, then ask `Find AWS waste in us-east-1`.

## What it finds

Unattached EBS volumes, gp2 volumes, idle Elastic IPs, stopped instances that still hold storage,
snapshots older than a year, and log groups that keep data forever.

## Good to know

- The script makes only `describe` calls and changes nothing. A test checks this.
- "Resolved" means the resource is no longer reported. Confirm the savings in Cost Explorer.
- The saved JSON files hold your account ID and resource IDs, so keep them private.
- Version 0.1 is tested on made-up data only. Please open an issue for a wrong finding.

Want scheduled scans without running a script? [Open this pre-filled issue](https://github.com/ravsau/aws-waste-proof/issues/new?title=I+want+a+hosted+version).

MIT License
