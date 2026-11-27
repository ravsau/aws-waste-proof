# aws-waste-proof

Find unused AWS resources, clean them up, then check they are gone. One Python file, read-only.

## Try it (no AWS account needed)

```bash
git clone https://github.com/ravsau/aws-waste-proof && python3 aws-waste-proof/waste.py demo
```

```text
4 resolved, 2 still open, 1 new, 0 unknown
```

followed by a table of each resource. The demo uses made-up data.

## Use it on your account

Needs Python 3.9+ and the AWS CLI, already logged in.

```bash
python3 waste.py scan --region us-east-1 --out before.json     # 1. see the waste
# 2. delete what you choose to delete
python3 waste.py scan --region us-east-1 --out after.json      # 3. scan again
python3 waste.py compare before.json after.json                # 4. see what is gone
```

## What it looks for

- EBS volumes attached to nothing
- gp2 volumes (gp3 is usually cheaper)
- Elastic IPs attached to nothing
- Stopped instances that still hold storage
- Snapshots older than a year
- Log groups that never delete logs

## Safe to run

`waste.py` only reads. It cannot create, change or delete anything in your account.
`before.json` and `after.json` contain your account ID, so do not share them.

Version 0.1 is tested on made-up data only. Found a wrong result? Open an issue.

Want this on a schedule, with no script to run? [Tell me here](https://github.com/ravsau/aws-waste-proof/issues/new?title=I+want+a+hosted+version).
