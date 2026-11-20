#!/usr/bin/env python3
"""Tests for brief.py, the weekly agentic commerce brief.
Runs on saved feeds in tests/fixtures, so it needs no network."""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..")
RSS = os.path.join(HERE, "fixtures", "feed.xml")
ATOM = os.path.join(HERE, "fixtures", "atom.xml")

spec = importlib.util.spec_from_file_location("brief", os.path.join(TOOL, "brief.py"))
brief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brief)

with open(os.path.join(TOOL, "sources.json")) as f:
    CFG = json.load(f)
NOW = dt.datetime(2026, 11, 19, 23, 0, tzinfo=dt.timezone.utc)

fails = 0


def check(cond, label):
    global fails
    print(("ok   " if cond else "FAIL ") + label)
    fails += 0 if cond else 1


def load(path, name):
    with open(path, "rb") as f:
        return brief.parse_feed(f.read(), name)


items = load(RSS, "fixture") + load(ATOM, "Atom fixture")
check(len(items) == 10, "parses 9 RSS items and 1 Atom entry")
check(items[0]["title"] == "Spreedly adds fraud checks for AI agent orders", "drops Google News' ' - Publisher' suffix")
check(items[0]["source"] == "The Paypers", "source comes from <source>")
check(not any(i["title"].startswith("CORRECTING") for i in items), "drops the press-wire 'CORRECTING and REPLACING' prefix")
check(items[-1]["date"] == dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc), "reads Atom ISO dates")

out = brief.build(items, CFG, NOW, 7)
titles = [s["title"] for v in out.values() for s in v]
names = [b["name"] for b in CFG["buckets"]]


def bucket_of(word):
    return next((n for n, v in out.items() for s in v if word.lower() in s["title"].lower()), None)


check(not any("savings rates" in t for t in titles), "drops an item that is not about agents")
check(not any(t.startswith("Old agentic") for t in titles), "drops an item older than the window")
check(not any("AWS Marketplace" in t for t in titles), "drops AWS Marketplace listing spam")
visa = out["Visa's own moves"]
check(len(visa) == 1 and len(visa[0]["also"]) == 1, "folds two outlets on the Visa story into one entry")
check(bucket_of("Spreedly") == "Fraud and disputes", "a fraud headline lands in Fraud and disputes")
check(bucket_of("Rakuten") == "Competitor moves", "a Mastercard headline lands in Competitor moves")
check(bucket_of("ChatGPT Wallet") == "New agent partners and merchants", "an OpenAI launch lands in partners")
check(bucket_of("EMVCo") == "Rules and standards", "an EMVCo standard lands in Rules and standards")
check(bucket_of("storytelling") == names[-1], "anything else on topic lands in the last bucket")
check(names[0] == "Fraud and disputes", "fraud is checked first, so a fraud story about Visa stays a fraud story")

check(brief.same_story("Yeahka, Mastercard Team Up on AI Agent Commerce",
                       "Yeahka and Mastercard Sign Agreement to Explore AI Agent-Driven Commerce"), "same story, two wordings")
check(not brief.same_story("Yeahka, Mastercard Team Up on AI Agent Commerce",
                           "Rakuten Teams With Mastercard to Power Agentic Commerce"), "two Mastercard deals stay apart")

md = brief.render(out, CFG, NOW, 7)
check(md.startswith("# Agentic commerce brief: Nov 12 to Nov 19, 2026"), "title names the window")
check("## Fraud and disputes (1)" in md and "+ 1 more" in md, "sections carry counts; folded stories say how many more outlets")
check("**My read this week:**" in md, "leaves a slot for my own read")

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "b.md")
    r = subprocess.run([sys.executable, os.path.join(TOOL, "brief.py"), "--feed-file", RSS, "--feed-file", ATOM,
                        "--now", "2026-11-19T23:00:00", "--out", path], capture_output=True, text=True)
    check(r.returncode == 0 and os.path.exists(path), "CLI writes the brief from saved feeds")
    check("6 stories" in open(path).read(), "CLI keeps 6 stories from the fixtures")

print(f"\n{'FAIL' if fails else 'PASS'}: {fails} failed")
sys.exit(1 if fails else 0)
