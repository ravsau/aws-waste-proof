# aws-waste-proof

**Find unused AWS resources. Clean them up. Prove they are gone.**

A Claude Code skill and a single Python script. The script scans your account with read-only AWS CLI calls, saves a report, and compares it with a second scan after your cleanup.

```text
4 resolved, 2 still open, 1 new, 0 unknown

Resolved
  gp2-volume               vol-gp2           100 GiB gp2 volume
  idle-elastic-ip          eipalloc-idle     Elastic IP with no association
  log-group-no-retention   /aws/lambda/demo  no retention policy, 5.00 GiB stored
  unattached-volume        vol-loose         500 GiB gp3 volume in state 'available'
Still open
  old-snapshot             snap-old          started 2023-03-01
  stopped-instance-storage i-stopped         stopped instance still holds 1 EBS volume
New
  unattached-volume        vol-new           20 GiB gp3 volume in state 'available'
```

The output above is shortened and comes from made-up data. Run it yourself with no AWS account:

```bash
git clone https://github.com/ravsau/aws-waste-proof && python3 aws-waste-proof/examples/demo.py
```

## Install in Claude Code

```text
/plugin marketplace add ravsau/aws-waste-proof
/plugin install aws-waste-proof@aws-waste-proof
```

Then ask: `Find AWS waste in us-east-1`.

## Or run the script alone

You need Python 3.9 or later and a configured AWS CLI.

```bash
cd aws-waste-proof/skills/aws-waste-proof
python3 scripts/waste.py scan --region us-east-1 --out before.json
# clean up what you decide to clean up
python3 scripts/waste.py scan --region us-east-1 --out after.json
python3 scripts/waste.py compare before.json after.json
```

## What the scan checks

| Check | Reports |
|---|---|
| `unattached-volume` | EBS volumes in state `available` |
| `gp2-volume` | gp2 volumes to compare against gp3 |
| `idle-elastic-ip` | Elastic IPs with no association |
| `stopped-instance-storage` | Stopped instances that still hold EBS volumes |
| `old-snapshot` | Your snapshots older than `--snapshot-days` (default 365) |
| `log-group-no-retention` | CloudWatch log groups that keep data forever |

## What "proof" means here

A finding is **resolved** only when the same check ran without error, in the same region of the same account, and no longer reports the resource. A denied permission or a skipped region shows up as **unknown**.

Resolved does not show that your bill went down. For example, a stopped instance that someone started again counts as resolved and costs more. Confirm savings in Cost Explorer.

The script prints no dollar estimates.

## Read-only by construction

The script can run only the operations in the `ALLOWED` list at the top of [`waste.py`](skills/aws-waste-proof/scripts/waste.py), and a test checks that each one is a `describe` or `get` call. The matching IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ec2:DescribeVolumes",
      "ec2:DescribeAddresses",
      "ec2:DescribeInstances",
      "ec2:DescribeSnapshots",
      "logs:DescribeLogGroups"
    ],
    "Resource": "*"
  }]
}
```

The script sends nothing anywhere except the AWS CLI calls. The saved JSON files hold your account ID and resource IDs, so keep them private. When an agent runs the skill, the findings go to the model that agent uses.

## Test

```bash
python3 tests/test_waste.py
```

The tests use made-up data. Version 0.1 has not been checked against a range of real accounts, so please [report wrong findings](https://github.com/ravsau/aws-waste-proof/issues).

## Want a hosted version?

If you want scheduled scans and before/after reports without running a script, [open this pre-filled issue](https://github.com/ravsau/aws-waste-proof/issues/new?title=I+want+a+hosted+version).

MIT License
