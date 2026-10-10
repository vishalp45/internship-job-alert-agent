"""Page-watch: finds NEW internship-related links/lines on career pages that have no ATS API.
  python page_watch.py --limit 5     test on the first 5 companies
  python page_watch.py --only Stripe check a single company
  python page_watch.py --email       full run, emails anything new
First time a company is seen it is only recorded as a baseline (no alert)."""
import argparse, csv, json, re, time
from urllib.parse import urljoin
import requests, yaml
from bs4 import BeautifulSoup

try:
    import playwright  # noqa: F401
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False
STATE = "seen.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0; personal use)"}
PRIORITY = {"dream": 0, "target": 1, "backup": 2}


def load_cfg():
    return yaml.safe_load(open("config.yaml", encoding="utf-8"))


def build_regex(words):
    return re.compile(r"\b(" + "|".join(re.escape(w.lower()) for w in words) + r")\b")


def fetch_plain(url):
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.text


def fetch_rendered(url):
    """Optional JS rendering. Needs: pip install playwright && playwright install chromium"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-http2"])      # fixes some HTTP2 protocol errors
        pg = b.new_page(user_agent=UA["User-Agent"])
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)   # best effort only
        except Exception:
            pass
        pg.wait_for_timeout(1500)                            # let job lists render
        html = pg.content()
        b.close()
    return html


def extract(html, base_url, hit, excl):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    items, link_texts = set(), set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(base_url, a["href"])
        hay = f"{text} {href}".lower()
        if hit.search(hay) and not any(x in hay for x in excl):
            items.add(f"{text[:120]} | {href}")
            link_texts.add(text.lower())
    for line in soup.get_text("\n").split("\n"):
        line = " ".join(line.split())
        if line.lower() in link_texts:
            continue
        if line.endswith(".") and len(line.split()) > 12:   # marketing sentence, not a posting
            continue
        if 3 <= len(line) <= 200 and hit.search(line.lower()) and not any(x in line.lower() for x in excl):
            items.add(f"text: {line}")
    return sorted(items)[:200]


def get_items(url, hit, excl):
    try:
        html = fetch_plain(url)
    except Exception as plain_err:        # blocked (403) or failed: try a real browser
        html = fetch_rendered(url)
        if html is None:
            raise plain_err
        return extract(html, url, hit, excl)
    items = extract(html, url, hit, excl)
    if len(BeautifulSoup(html, "html.parser").get_text()) < 500:   # probably JS-only page
        rendered = fetch_rendered(url)
        if rendered:
            items = extract(rendered, url, hit, excl)
    return items


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run(limit=None, only=None):
    cfg = load_cfg()
    hit = build_regex(cfg["page_watch_keywords"])
    excl = [w.lower() for w in cfg["roles_exclude"]]
    rows = [r for r in csv.DictReader(open("companies.csv", encoding="utf-8")) if r["check_method"] in (("page_watch", "needs_browser") if HAS_BROWSER else ("page_watch",))]
    if only:
        rows = [r for r in rows if r["company"].lower() == only.lower()]
    if limit:
        rows = rows[:limit]

    state = load_state()
    watch = state.setdefault("page_watch", {})
    new, failed, baselined = [], [], 0

    for r in rows:
        urls = list(dict.fromkeys(u for u in (r["early_careers_url"], r["careers_url"]) if u))
        items, ok = set(), False
        for u in urls:
            try:
                items.update(get_items(u, hit, excl))
                ok = True
            except Exception as e:
                print(f"  ! {r['company']}: {u} -> {str(e)[:90]}")
            time.sleep(1.5)                                         # be polite
        if not ok:
            failed.append(r["company"])
            continue
        prev = watch.get(r["company"])
        if prev is None:
            watch[r["company"]] = sorted(items)
            baselined += 1
        else:
            fresh = sorted(items - set(prev))
            if fresh:
                new.append((r["company"], r["priority"], urls[0], fresh))
            watch[r["company"]] = sorted(set(prev) | items)

    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=1)
    return dict(checked=len(rows), failed=failed, baselined=baselined, new=new)


def format_digest(res):
    new = sorted(res["new"], key=lambda x: PRIORITY.get(x[1], 3))
    lines = [f"Checked {res['checked']} · baselined {res['baselined']} · failed {len(res['failed'])} · new {len(new)}", ""]
    for company, prio, url, items in new:
        lines.append(f"{company} [{prio or 'unranked'}] - {url}")
        lines += [f"   • {i}" for i in items[:10]]
        lines.append("")
    if res["failed"]:
        lines.append("Could not load: " + ", ".join(res["failed"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--email", action="store_true")
    ap.add_argument("--status", action="store_true", help="email a status summary even if nothing is new")
    a = ap.parse_args(argv)
    try:
        orig_state = open(STATE, encoding="utf-8").read()
    except FileNotFoundError:
        orig_state = None
    res = run(a.limit, a.only)
    body = format_digest(res)
    print(body)
    if a.email and (res["new"] or a.status):
        from notify_email import send_email
        if res["new"]:
            subject = f"Job Agent: {len(res['new'])} company page(s) with new postings"
        else:
            subject = "Job Agent: weekly status - running fine, nothing new"
        try:
            send_email(subject, body)
        except Exception:
            if orig_state is not None:      # undo, so these finds are reported on the next run
                open(STATE, "w", encoding="utf-8").write(orig_state)
            print("Email failed: state restored, these finds will be reported next run.")
            raise
        print("Email sent.")


if __name__ == "__main__":
    main()
