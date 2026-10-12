"""Page-watch: finds NEW internship-related links/lines on career pages that have no ATS API.
  python page_watch.py --limit 5     test on the first 5 companies
  python page_watch.py --only Stripe check a single company
  python page_watch.py --email       full run, emails anything new
First time a company is seen it is only recorded as a baseline (no alert)."""
import argparse, csv, json, re, time
from urllib.parse import urljoin
import requests, yaml
import ats_fetch
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
    fits = make_fit(cfg)
    friend_fits = make_friend_fit(cfg)
    hit = build_regex(cfg["page_watch_keywords"])
    excl = [w.lower() for w in cfg["roles_exclude"] if w.lower() != "manager"]
    rows = [r for r in csv.DictReader(open("companies.csv", encoding="utf-8")) if r["check_method"] in (("page_watch", "needs_browser", "api") if HAS_BROWSER else ("page_watch", "api"))]
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
        if r["check_method"] == "api":
            try:
                items.update(ats_fetch.fetch(r, hit, excl))
                ok = True
            except Exception as e:
                print(f"  ! {r['company']}: API -> {str(e)[:90]}")
            time.sleep(1)
        else:
            for u in urls:
                try:
                    items.update(get_items(u, hit, excl))
                    ok = True
                except Exception as e:
                    print(f"  ! {r['company']}: {u} -> {str(e)[:90]}")
                time.sleep(1.5)                                     # be polite
        if not ok:
            failed.append(r["company"])
            continue
        items = {i for i in items if fits(i) or friend_fits(i)}
        prev = watch.get(r["company"])
        if prev is None:
            watch[r["company"]] = sorted(items)
            baselined += 1
        else:
            fresh = sorted(items - set(prev))
            if cfg.get("check_links", True):
                fresh = [i for i in fresh if link_alive(i)]
            if fresh:
                new.append((r["company"], r["priority"], urls[0], fresh))
            watch[r["company"]] = sorted(set(prev) | items)

    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=1)
    return dict(checked=len(rows), failed=failed, baselined=baselined, new=new)


INTERN_WORDS = ["intern", "interns", "internship", "internships", "co-op", "summer analyst"]

# Role families taken from the resumes (SDE, AI/ML, Mechanical) plus photography and product management.
FIT_FAMILIES = {
    "SDE": ["software", "sde", "swe", "developer", "development", "backend", "back-end", "frontend",
            "front-end", "full stack", "full-stack", "fullstack", "web", "api", "mobile", "android", "ios",
            "cloud", "devops", "sre", "platform", "systems", "security", "sdet", "python", "java", "c++",
            "technology", "technical"],
    "AI/ML": ["machine learning", "ml", "ai", "artificial intelligence", "genai", "generative ai", "llm",
              "nlp", "computer vision", "deep learning", "data", "analytics", "research", "scientist",
              "statistics", "quant", "quantitative"],
    "Mechanical": ["mechanical", "mechatronics", "robotics", "cad", "solidworks", "autocad", "ansys", "cfd",
                   "fea", "finite element", "thermal", "thermodynamics", "manufacturing", "fabrication",
                   "aerospace", "automotive", "design engineer", "product design", "production engineer",
                   "heat transfer", "fluid", "welding", "casting", "machine design", "kinematics",
                   "simulation", "industrial", "r&d", "research and development", "process engineer"],
    "Photography": ["photography", "photographer", "photo", "photos", "photojournalism", "videography",
                    "videographer", "video", "cinematography", "visual", "multimedia", "creative",
                    "content creator", "content creation"],
    "Product": ["product", "product manager", "product management", "apm", "associate product manager",
                "product analyst", "product owner", "program manager", "technical program"],
    "Engineering": ["engineer", "engineering"],
}
FIT_NOT = ["sales", "marketing", "hr", "human resources", "recruiter", "recruiting", "talent", "finance",
           "financial", "accounting", "audit", "tax", "legal", "procurement", "supply chain", "operations",
           "business", "customer success", "customer support", "brand", "communications", "market", "ux",
           "graphic", "analog", "vlsi", "asic", "fpga", "civil", "chemical", "electrical", "phd", "ph.d",
           "mba", "master", "masters", "postdoc", "post-doctoral", "senior", "staff", "principal",
           "director"]


SOFTWARE_BLOCK = ["software", "sde", "swe", "developer", "backend", "frontend", "full stack", "web", "machine learning",
                  "data", "ai", "product", "cloud", "devops", "qa", "mobile", "android", "ios"]
HARDWARE_BLOCK = ["hardware", "embedded", "firmware", "rtl", "silicon", "chip", "soc"]

# Friend section: electrical engineering student
FRIEND_FAMILIES = {
    "Electrical/ECE": ["electrical", "electronics", "electronic", "ece", "eee", "circuit", "circuits", "pcb",
                       "power systems", "power system", "power electronics", "control systems", "control system",
                       "signal processing", "iot", "ev", "electric vehicle", "battery", "plc", "scada",
                       "automation"],
    "Hardware/Embedded": ["embedded", "firmware", "hardware", "analog", "verification"],
}
FRIEND_NOT = ["sales", "marketing", "hr", "human resources", "recruiter", "recruiting", "talent", "finance",
              "financial", "accounting", "audit", "tax", "legal", "procurement", "supply chain", "operations",
              "business", "customer success", "customer support", "brand", "market", "ux", "graphic", "civil",
              "chemical", "mechanical", "phd", "ph.d", "mba", "master", "masters", "postdoc", "post-doctoral",
              "senior", "staff", "principal", "director"]


def _build_fit(families, bad_words, blockers, strict=True):
    intern = build_regex(INTERN_WORDS)
    bad = build_regex(bad_words)
    fam = {k: build_regex(v) for k, v in families.items()}
    block = build_regex(blockers)
    pm = re.compile(r"\b(product|program)\b")

    def title(item):
        return item.split(" | ")[0].lower()

    def tags(item):
        t = title(item)
        strong = [k for k, rx in fam.items() if k != "Engineering" and rx.search(t)]
        if strong:
            return strong
        if "Engineering" in fam and fam["Engineering"].search(t) and not block.search(t):
            return ["Engineering"]
        return []

    def fits(item):
        t = title(item)
        if not intern.search(t) or bad.search(t):
            return False
        if re.search(r"\bmanager\b", t) and not pm.search(t):
            return False
        return bool(tags(item)) if strict else True

    fits.tags = tags
    return fits


def make_fit(cfg):
    """fits(item) keeps internships that match your role families; fits.tags(item) lists them."""
    if not cfg.get("profile_filter", True):
        fits = lambda item: True
        fits.tags = lambda item: []
        return fits
    return _build_fit(cfg.get("fit_families", FIT_FAMILIES), cfg.get("fit_exclude", FIT_NOT),
                      cfg.get("hardware_block", HARDWARE_BLOCK), cfg.get("profile_strict", True))


def make_friend_fit(cfg):
    """Same idea for the friend (electrical engineering) section. Off if friend_section: false."""
    if not cfg.get("profile_filter", True) or not cfg.get("friend_section", True):
        fits = lambda item: False
        fits.tags = lambda item: []
        return fits
    return _build_fit(cfg.get("friend_families", FRIEND_FAMILIES), cfg.get("friend_exclude", FRIEND_NOT),
                      cfg.get("software_block", SOFTWARE_BLOCK), True)


URL_RX = re.compile(r"https?://[^\s]+")
DEAD_PHRASES = ["no longer accepting", "no longer available", "position has been filled", "job has expired",
                "this job is closed", "posting has expired", "page not found"]


def link_alive(item):
    """False only if the apply link is clearly dead or closed. Anything uncertain counts as alive."""
    m = URL_RX.search(item)
    if not m:
        return True
    try:
        r = requests.get(m.group(0), headers=UA, timeout=12, allow_redirects=True)
        if r.status_code in (404, 410):
            return False
        if re.search(r"/404|not-?found", r.url.lower()):
            return False
        return not any(p in r.text[:30000].lower() for p in DEAD_PHRASES)
    except Exception:
        return True


INDIA_WORDS = ["india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "gurgaon",
               "gurugram", "noida", "chennai", "kolkata", "ahmedabad", "kochi", "coimbatore",
               "thiruvananthapuram", "jaipur", "indore", "chandigarh", "mohali", "vadodara", "nagpur"]


def region_split(res, fit=None):
    """Splits new finds into India entries and everything else, each sorted by priority."""
    rx = build_regex(load_cfg().get("india_keywords", INDIA_WORDS))
    india, other = [], []
    for company, prio, url, items in res["new"]:
        if fit is not None:
            items = [i for i in items if fit(i)]
        ind = [i for i in items if rx.search(i.lower()) or "/en-in/" in i.lower()]
        rest = [i for i in items if i not in ind]
        if ind:
            india.append((company, prio, url, ind))
        if rest:
            other.append((company, prio, url, rest))
    key = lambda x: PRIORITY.get(x[1], 3)
    return sorted(india, key=key), sorted(other, key=key)


def tag_text(item, fit):
    t = fit.tags(item)
    return f"   [{', '.join(t)}]" if t else ""


def format_digest(res):
    cfg = load_cfg()
    mine, friend = make_fit(cfg), make_friend_fit(cfg)
    lines = [f"Checked {res['checked']} · baselined {res['baselined']} · failed {len(res['failed'])} · new {len(res['new'])}", ""]
    for banner, fit in ((None, mine), ("##### FOR YOUR FRIEND (Electrical Engineering) #####", friend)):
        india, other = region_split(res, fit)
        if not (india or other):
            continue
        if banner:
            lines += [banner, ""]
        for title, entries in (("=== INDIA ===", india), ("=== OTHER LOCATIONS / NOT STATED ===", other)):
            if not entries:
                continue
            lines += [title, ""]
            for company, prio, url, items in entries:
                lines.append(f"{company} [{prio or 'unranked'}] - {url}")
                lines += [f"   • {i}{tag_text(i, fit)}" for i in items[:10]]
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
            cfg = load_cfg()
            india, other = region_split(res, make_fit(cfg))
            f_in, f_other = region_split(res, make_friend_fit(cfg))
            n_in, n_other = sum(len(e[3]) for e in india), sum(len(e[3]) for e in other)
            n_friend = sum(len(e[3]) for e in f_in + f_other)
            subject = f"Job Agent: {n_in} India + {n_other} other new postings"
            if n_friend:
                subject += f" · friend: {n_friend}"
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
