"""Checks every URL in companies.csv and reports the broken ones.
  python check_urls.py
Writes url_report.csv (all results) and prints the ones that need fixing."""
import csv, re
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BAD_URL = re.compile(r"/404|not-?found|page-?not|/error|/oops", re.I)
BAD_TITLE = re.compile(r"not found|404|page (can.?t|cannot) be found|doesn.?t exist|no longer available", re.I)


def classify(status, final_url, title):
    if status in (404, 410):
        return "NOT_FOUND"
    if status in (401, 403, 429, 999):
        return "BLOCKED"          # bot protection; usually fine in a normal browser
    if status >= 400:
        return "ERROR"
    if BAD_URL.search(final_url) or BAD_TITLE.search(title or ""):
        return "SOFT_404"         # loads, but it is an error/redirect page
    return "OK"


def check(url):
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text[:20000], re.I | re.S)
        title = " ".join(m.group(1).split())[:80] if m else ""
        return url, classify(r.status_code, r.url, title), r.status_code, r.url, title
    except Exception as e:
        return url, "ERROR", 0, "", type(e).__name__


if __name__ == "__main__":
    rows = list(csv.DictReader(open("companies.csv", encoding="utf-8")))
    jobs = []
    for r in rows:
        for col in ("early_careers_url", "careers_url"):
            if r[col]:
                jobs.append((r["company"], col, r[col]))
    urls = sorted({u for _, _, u in jobs})
    print(f"Checking {len(urls)} unique URLs...")
    with ThreadPoolExecutor(8) as ex:
        res = {x[0]: x for x in ex.map(check, urls)}

    with open("url_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "column", "url", "verdict", "status", "final_url", "title"])
        for company, col, u in jobs:
            _, v, s, fu, t = res[u]
            w.writerow([company, col, u, v, s, fu, t])

    counts = {}
    for company, col, u in jobs:
        v = res[u][1]
        counts[v] = counts.get(v, 0) + 1
        if v in ("NOT_FOUND", "SOFT_404", "ERROR"):
            print(f"{v:9} {company} [{col}] {u}")
    print("\nSummary:", counts)
    print("BLOCKED = site refuses scripts (probably fine in a browser). Full list in url_report.csv")
