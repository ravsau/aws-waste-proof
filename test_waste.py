import datetime as dt
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import waste  # noqa: E402

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def load(name):
    return json.loads((ROOT / name.replace("aws-", "demo-")).read_text())


def runner(responses, fail=()):
    def run(service, operation, region, extra=()):
        if operation in fail:
            raise waste.AwsError("AccessDenied")
        return responses[operation]
    return run


def scan(name, **kw):
    return waste.scan(["us-east-1"], run=runner(load(name), **kw), now=NOW)


class ScanTest(unittest.TestCase):
    def test_finds_each_kind_and_skips_healthy_resources(self):
        ids = sorted(f["id"] for f in scan("aws-before.json")["findings"])
        self.assertEqual(ids, [
            "gp2-volume:us-east-1:vol-gp2",
            "idle-elastic-ip:us-east-1:eipalloc-idle",
            "log-group-no-retention:us-east-1:/aws/lambda/demo",
            "old-snapshot:us-east-1:snap-old",
            "stopped-instance-storage:us-east-1:i-stopped",
            "unattached-volume:us-east-1:vol-loose",
        ])

    def test_failed_check_is_reported_and_not_marked_complete(self):
        report = scan("aws-before.json", fail=("describe-addresses",))
        self.assertEqual(report["errors"][0]["check"], "idle-elastic-ip")
        self.assertNotIn("idle-elastic-ip:us-east-1", report["completed"])
        self.assertIn("NOT checked", waste.render_scan(report))

    def test_write_operations_are_blocked(self):
        with self.assertRaises(ValueError):
            waste.aws("ec2", "delete-volume", "us-east-1")

    def test_every_allowed_operation_reads(self):
        for _, operation in waste.ALLOWED:
            self.assertTrue(operation.startswith(("describe-", "get-")), operation)


class CompareTest(unittest.TestCase):
    def test_resolved_still_open_and_new(self):
        result = waste.compare(scan("aws-before.json"), scan("aws-after.json"))
        self.assertEqual(len(result["resolved"]), 4)
        self.assertEqual(len(result["still_open"]), 2)
        self.assertEqual([f["resource"] for f in result["new"]], ["vol-new"])
        self.assertEqual(result["unknown"], [])

    def test_failed_check_never_counts_as_resolved(self):
        after = scan("aws-after.json", fail=("describe-addresses",))
        result = waste.compare(scan("aws-before.json"), after)
        self.assertIn("eipalloc-idle", [f["resource"] for f in result["unknown"]])
        self.assertNotIn("eipalloc-idle", [f["resource"] for f in result["resolved"]])

    def test_region_left_out_of_second_scan_is_unknown(self):
        after = waste.scan(["eu-west-1"], run=runner(load("aws-after.json")), now=NOW)
        result = waste.compare(scan("aws-before.json"), after)
        self.assertEqual(result["resolved"], [])

    def test_check_missing_from_first_scan_is_not_called_new(self):
        before = scan("aws-before.json", fail=("describe-addresses",))
        result = waste.compare(before, scan("aws-before.json"))
        self.assertEqual(result["new"], [])
        self.assertEqual(len(result["unknown"]), 1)

    def test_different_accounts_or_settings_are_refused(self):
        before = scan("aws-before.json")
        with self.assertRaises(ValueError):
            waste.compare(before, {**before, "account": "999999999999"})
        with self.assertRaises(ValueError):
            waste.compare(before, {**before, "snapshot_days": 30})


if __name__ == "__main__":
    unittest.main()
