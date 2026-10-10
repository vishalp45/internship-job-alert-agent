"""One-time script: fills ats_type and slug in companies.csv from the careers URL.
No network, no LLM. Run: python detect_ats.py"""
import csv, re

PATTERNS = [
    ("greenhouse", r"(?:boards|job-boards)\.greenhouse\.io/([\w-]+)"),
    ("lever",      r"jobs\.lever\.co/([\w-]+)"),
    ("ashby",      r"jobs\.ashbyhq\.com/([\w.-]+)"),
    ("workday",    r"([\w-]+)\.wd\d+\.myworkdayjobs\.com/(?:[\w-]+/)?([\w-]+)"),
]

rows = list(csv.DictReader(open("companies.csv", encoding="utf-8")))
for r in rows:
    r["ats_type"], r["slug"] = "custom", ""
    for url in (r["careers_url"], r.get("early_careers_url", "")):
        for name, pat in PATTERNS:
            m = re.search(pat, url or "")
            if m:
                r["ats_type"] = name
                r["slug"] = "/".join(m.groups())  # workday: tenant/site
                break
        if r["ats_type"] != "custom":
            break
    if r["ats_type"] != "custom":
        r["check_method"] = "api"

with open("companies.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print({r["company"]: r["ats_type"] for r in rows})
