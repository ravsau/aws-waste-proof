#!/usr/bin/env python3
"""Run a before/after comparison on made-up data. No AWS account needed."""
import datetime as dt
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills/aws-waste-proof/scripts"))
import waste  # noqa: E402


def scan(name):
    data = json.loads((HERE / name).read_text())
    return waste.scan(["us-east-1"], run=lambda s, operation, r, extra=(): data[operation],
                      now=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))


print(waste.render_compare(waste.compare(scan("aws-before.json"), scan("aws-after.json"))))
