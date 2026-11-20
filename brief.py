#!/usr/bin/env python3
"""brief.py: a weekly agentic commerce brief from news feeds, sorted into buckets.

Reads sources.json (Google News searches plus a few trade feeds), keeps the items from the
last N days that are about agents buying things, folds several outlets on one story into one
entry, sorts each story into the first bucket whose pattern matches its title (then its summary),
ranks each bucket by how many outlets ran the story, and writes markdown to briefs/YYYY-MM-DD.md.

    python3 brief.py                       # last 7 days -> briefs/<today>.md
    python3 brief.py --days 14 --stdout    # print instead of writing a file
    python3 brief.py --json out.json       # also save the items as JSON
    python3 brief.py --feed-file a.xml     # read saved feed files, no network (tests, offline)

Standard library only, no API keys. A feed that fails is named at the end of the brief, not fatal.
"""
import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (agentic-brief; +stdlib urllib)"
ATOM = "{http://www.w3.org/2005/Atom}"


def google_news_url(query, days):
    q = urllib.parse.quote_plus(f"{query} when:{days}d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _text(el, tag):
    found = el.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def _date(raw):
    if not raw:
        return None
    try:
        d = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _plain(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_feed(data, feed_name):
    """RSS 2.0 or Atom bytes -> list of {title, link, source, date, summary}."""
    root = ET.fromstring(data)
    items = []
    for it in root.iter("item"):
        src = it.find("source")
        title = _plain(_text(it, "title"))
        source = (src.text or "").strip() if src is not None and src.text else feed_name
        # Google News puts " - Publisher" on the end of every title.
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        title = re.sub(r"^CORRECTING and REPLACING:?\s*", "", title, flags=re.I)
        items.append({
            "title": title,
            "link": _text(it, "link"),
            "source": source,
            "date": _date(_text(it, "pubDate")),
            "summary": _plain(_text(it, "description"))[:400],
        })
    for it in root.iter(ATOM + "entry"):
        link = it.find(ATOM + "link")
        items.append({
            "title": _plain(_text(it, ATOM + "title")),
            "link": link.get("href", "") if link is not None else "",
            "source": feed_name,
            "date": _date(_text(it, ATOM + "updated") or _text(it, ATOM + "published")),
            "summary": _plain(_text(it, ATOM + "summary"))[:400],
        })
    return items


STOP = set("""a an and the for with from into onto over that this its their your our to of in on at by as is are be
will can could new now more how why what who when where via amid after says said report reports
ai agent agents agentic commerce payment payments pay shopping shop""".split())


def _key(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _words(title):
    return {w for w in _key(title).split() if len(w) > 2 and w not in STOP}


def same_story(a, b):
    """Two outlets on one story: most of the shorter title's distinctive words are shared."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    shared = len(wa & wb)
    return shared >= 2 and shared / min(len(wa), len(wb)) >= 0.5


def build(items, cfg, now, days):
    """Keep on-topic items from the window, fold several outlets on one story into one entry,
    sort into buckets, and rank each bucket by how many outlets covered the story, then date."""
    since = now - dt.timedelta(days=days)
    topic = re.compile(cfg["topic"], re.I)
    exclude = re.compile(cfg["exclude"], re.I) if cfg.get("exclude") else None
    stories = []
    for it in sorted(items, key=lambda i: i["date"] or since, reverse=True):
        if not it["title"] or not it["date"] or it["date"] < since or it["date"] > now + dt.timedelta(days=1):
            continue
        text = f'{it["title"]} {it["summary"]}'
        if not topic.search(text) or (exclude and exclude.search(text)):
            continue
        twin = next((s for s in stories if _key(s["title"]) == _key(it["title"]) or same_story(s["title"], it["title"])), None)
        if twin:
            if it["source"] not in twin["also"] and it["source"] != twin["source"]:
                twin["also"].append(it["source"])
            continue
        stories.append(dict(it, also=[]))

    pats = [(b["name"], re.compile(b["pattern"], re.I) if b["pattern"] else None) for b in cfg["buckets"]]
    out = {name: [] for name, _ in pats}
    for st in stories:
        # The title decides first; the summary only places what the title alone cannot.
        name = next((n for n, p in pats if p and p.search(st["title"])), None)
        name = name or next((n for n, p in pats if p is None or p.search(st["summary"])), None)
        out[name].append(st)
    for name in out:
        out[name].sort(key=lambda s: (len(s["also"]), s["date"]), reverse=True)
    return out


def render(sorted_items, cfg, now, days, failed=(), per_bucket=8):
    start = (now - dt.timedelta(days=days)).strftime("%b %-d")
    total = sum(len(v) for v in sorted_items.values())
    lines = [
        f"# Agentic commerce brief: {start} to {now.strftime('%b %-d, %Y')}",
        "",
        f"{total} stories from the last {days} days. In each section, the stories the most outlets covered come first.",
        "",
        "**My read this week:** _(three lines: what changed, who it hurts or helps, what I'd look into)_",
        "",
    ]
    for b in cfg["buckets"]:
        rows = sorted_items[b["name"]]
        if not rows:
            continue
        lines += [f"## {b['name']} ({len(rows)})", "", f"_{b['why']}_", ""]
        for it in rows[:per_bucket]:
            more = f" + {len(it['also'])} more" if it["also"] else ""
            lines.append(f"- [{it['title']}]({it['link']}) · {it['source']}{more} · {it['date'].strftime('%b %-d')}")
        if len(rows) > per_bucket:
            lines.append(f"- …and {len(rows) - per_bucket} more in the JSON output")
        lines.append("")
    if failed:
        lines += ["## Feeds that failed this run", ""] + [f"- {f}" for f in failed] + [""]
    return "\n".join(lines)


def collect(cfg, days, feed_files=None):
    items, failed = [], []
    if feed_files:
        for path in feed_files:
            with open(path, "rb") as f:
                items += parse_feed(f.read(), os.path.basename(path))
        return items, failed
    sources = [(f"Google News: {q}", google_news_url(q, days)) for q in cfg["queries"]]
    sources += [(f["name"], f["url"]) for f in cfg["feeds"]]
    for name, url in sources:
        try:
            items += parse_feed(fetch(url), name)
        except Exception as e:  # one bad feed should not sink the brief
            failed.append(f"{name}: {type(e).__name__}: {e}")
    return items, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, help="window in days (default: sources.json, 7)")
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--out", help="markdown path (default: briefs/<today>.md)")
    ap.add_argument("--stdout", action="store_true", help="print the brief instead of writing it")
    ap.add_argument("--json", help="also write every kept item to this JSON file")
    ap.add_argument("--feed-file", action="append", help="read a saved feed instead of the network")
    ap.add_argument("--now", help="pretend today is this ISO date (tests)")
    a = ap.parse_args(argv)

    with open(a.sources) as f:
        cfg = json.load(f)
    days = a.days or cfg.get("days", 7)
    now = dt.datetime.fromisoformat(a.now).replace(tzinfo=dt.timezone.utc) if a.now else dt.datetime.now(dt.timezone.utc)

    items, failed = collect(cfg, days, a.feed_file)
    sorted_items = build(items, cfg, now, days)
    md = render(sorted_items, cfg, now, days, failed)

    if a.json:
        with open(a.json, "w") as f:
            json.dump({k: [dict(i, date=i["date"].isoformat()) for i in v] for k, v in sorted_items.items()},
                      f, indent=1, ensure_ascii=False)
    if a.stdout:
        print(md)
    else:
        out = a.out or os.path.join(HERE, "briefs", now.strftime("%Y-%m-%d") + ".md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            f.write(md)
        kept = sum(len(v) for v in sorted_items.values())
        print(f"wrote {out}: {kept} stories from {len(items)} feed items, {len(failed)} feeds failed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
