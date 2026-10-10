"""Direct job-feed fetchers for companies on Greenhouse, Lever, Ashby and Workday.
Used by page_watch.py for rows whose check_method is 'api'. Returns strings: 'Title (Location) | link'."""
import re, time
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0; personal use)"}
WD = re.compile(r"https?://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)")
WD_SEARCH = ["intern", "2027", "graduate", "campus"]


def _ok(title, hit, excl):
    t = title.lower()
    return bool(hit.search(t)) and not any(x in t for x in excl)


def _line(title, loc, url):
    return f"{title} ({loc}) | {url}" if loc else f"{title} | {url}"


def greenhouse(slug, hit, excl):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", headers=UA, timeout=20)
    r.raise_for_status()
    return {_line(j["title"], (j.get("location") or {}).get("name", ""), j["absolute_url"])
            for j in r.json().get("jobs", []) if _ok(j["title"], hit, excl)}


def lever(slug, hit, excl):
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", headers=UA, timeout=20)
    r.raise_for_status()
    return {_line(j["text"], (j.get("categories") or {}).get("location", ""), j["hostedUrl"])
            for j in r.json() if _ok(j["text"], hit, excl)}


def ashby(slug, hit, excl):
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=UA, timeout=20)
    r.raise_for_status()
    return {_line(j["title"], j.get("location", ""), j.get("jobUrl", ""))
            for j in r.json().get("jobs", []) if _ok(j["title"], hit, excl)}


def workday(row, hit, excl):
    m = next((WD.search(row[c]) for c in ("careers_url", "early_careers_url") if WD.search(row.get(c) or "")), None)
    if not m:
        raise ValueError("no myworkdayjobs.com URL in this row")
    tenant, wd, site = m.groups()
    host = f"{tenant}.{wd}.myworkdayjobs.com"
    out = set()
    for word in WD_SEARCH:
        for offset in (0, 20, 40):                     # up to 60 results per search word
            r = requests.post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs", headers=UA, timeout=20,
                              json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": word})
            r.raise_for_status()
            posts = r.json().get("jobPostings", [])
            for j in posts:
                if _ok(j.get("title", ""), hit, excl):
                    out.add(_line(j["title"], j.get("locationsText", ""), f"https://{host}/{site}{j['externalPath']}"))
            if len(posts) < 20:
                break
            time.sleep(0.5)
        time.sleep(0.5)
    return out


def fetch(row, hit, excl):
    kind, slug = row["ats_type"], row["slug"]
    if kind == "greenhouse":
        return greenhouse(slug, hit, excl)
    if kind == "lever":
        return lever(slug, hit, excl)
    if kind == "ashby":
        return ashby(slug, hit, excl)
    if kind == "workday":
        return workday(row, hit, excl)
    raise ValueError(f"no API fetcher for ats_type '{kind}'")
