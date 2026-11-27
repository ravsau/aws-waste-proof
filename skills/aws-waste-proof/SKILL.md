---
name: aws-waste-proof
description: Find unused AWS resources with a read-only scan, then prove which ones are gone with a second scan. Use for "find AWS waste", "audit my AWS account for unused resources", "cut my AWS bill", or "check that the cleanup worked".
---

# aws-waste-proof

Run `scripts/waste.py` from this skill's folder. It needs Python 3.9+ and a configured AWS CLI.

1. Ask which AWS account profile and regions to scan if the user did not say. Set `AWS_PROFILE` for a named profile.
2. Scan: `python3 scripts/waste.py scan --region <region> --out aws-waste-before.json`
3. Report the findings. List every failed check and say those resources were not checked.
4. For each finding, show the `verify` command and say what the user must confirm before a change
   (owner, backups, AMIs, DNS records that point at an Elastic IP).
5. The user makes the changes. Never run an AWS command that creates, changes, or deletes anything.
6. After the changes, scan again with the same regions into `aws-waste-after.json`, then run
   `python3 scripts/waste.py compare aws-waste-before.json aws-waste-after.json`.
7. "Resolved" means the check no longer reports the resource. It does not show that the bill went down.
   A stopped instance that was started again is resolved and now costs more. Confirm savings in Cost Explorer.

The saved JSON files hold the AWS account ID and resource IDs. Keep them out of git.
