"""Event watcher: hackathons and competitions.
  A) watches the event pages in events.csv for new register/apply/deadline links or lines
  B) discovers new hackathons on Devpost (open or upcoming, online or in India)
  python event_watch.py --limit 3     test on a few events
  python event_watch.py --email       full run, emails anything new
First time something is seen it is only recorded as a baseline (no alert)."""
import argparse, csv, json, time
import requests
import page_watch as pw

DEFAULT_KEYWORDS = ["register", "registration", "apply now", "applications open", "now open",
                    "deadline", "last date", "sign up", "round 1", "2027"]
DEFAULT_LOCATIONS = ["online", "india"]


def fetch_devpost(locations):
    out = set()
    for page in (1, 2):
        r = requests.get("https://devpost.com/api/hackathons", headers=pw.UA, timeout=20,
                         params=[("status[]", "upcoming"), ("status[]", "open"),
                                 ("order_by", "deadline"), ("page", page)])
        r.raise_for_status()
        for h in r.json().get("hackathons", []):
            loc = (h.get("displayed_location") or {}).get("location", "")
            if any(x in loc.lower() for x in locations):
                out.add(f"{h['title']} ({loc}; {h.get('submission_period_dates', '')}) | {h['url']}")
    return out


def run(limit=None, only=None):
    cfg = pw.load_cfg()
    hit = pw.build_regex(cfg.get("event_keywords", DEFAULT_KEYWORDS))
    locations = [x.lower() for x in cfg.get("event_locations", DEFAULT_LOCATIONS)]
    rows = [r for r in csv.DictReader(open("events.csv", encoding="utf-8")) if r["link_quality"] == "direct"]
    if only:
        rows = [r for r in rows if only.lower() in r["event"].lower()]
    if limit:
        rows = rows[:limit]

    state = pw.load_state()
    watch = state.setdefault("event_watch", {})
    new, failed, baselined = [], [], 0

    def record(name, kind, url, items):
        nonlocal baselined
        prev = watch.get(name)
        if prev is None:
            watch[name] = sorted(items)
            baselined += 1
        else:
            fresh = sorted(items - set(prev))
            if fresh:
                new.append((name, kind, url, fresh))
            watch[name] = sorted(set(prev) | items)

    for r in rows:
        urls = list(dict.fromkeys(u for u in (r["event_url"], r["registration_url"]) if u))
        items, ok = set(), False
        for u in urls:
            try:
                items.update(pw.get_items(u, hit, []))
                ok = True
            except Exception as e:
                print(f"  ! {r['event']}: {u} -> {str(e)[:90]}")
            time.sleep(1.5)
        if ok:
            record(r["event"], r["type"], urls[0], items)
        else:
            failed.append(r["event"])

    if not only and not limit:
        try:
            record("Devpost discovery", "new hackathons", "https://devpost.com/hackathons", fetch_devpost(locations))
        except Exception as e:
            print(f"  ! Devpost discovery -> {str(e)[:90]}")
            failed.append("Devpost discovery")

    json.dump(state, open(pw.STATE, "w", encoding="utf-8"), indent=1)
    return dict(checked=len(rows), failed=failed, baselined=baselined, new=new)


def format_digest(res):
    lines = [f"Checked {res['checked']} events · baselined {res['baselined']} · failed {len(res['failed'])} · new {len(res['new'])}", ""]
    for name, kind, url, items in res["new"]:
        lines.append(f"{name} [{kind}] - {url}")
        lines += [f"   • {i}" for i in items[:8]]
        lines.append("")
    if res["failed"]:
        lines.append("Could not load: " + ", ".join(res["failed"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--email", action="store_true")
    a = ap.parse_args(argv)
    try:
        orig_state = open(pw.STATE, encoding="utf-8").read()
    except FileNotFoundError:
        orig_state = None
    res = run(a.limit, a.only)
    body = format_digest(res)
    print(body)
    if a.email and res["new"]:
        from notify_email import send_email
        try:
            send_email(f"Job Agent: {len(res['new'])} event update(s)", body)
        except Exception:
            if orig_state is not None:
                open(pw.STATE, "w", encoding="utf-8").write(orig_state)
            print("Email failed: state restored, these finds will be reported next run.")
            raise
        print("Email sent.")


if __name__ == "__main__":
    main()
