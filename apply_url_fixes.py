"""Applies the URL fixes found by check_urls.py to YOUR companies.csv (keeps your priority edits).
  python apply_url_fixes.py"""
import csv, json

NEW_EARLY = {   # company -> replacement early_careers_url
    "Salesforce": "https://www.salesforce.com/company/careers/university/internships/",
    "Workday": "https://www.workday.com/en-in/company/careers/early-career.html",
    "JPMorgan Chase (JPMC)": "https://www.jpmorganchase.com/careers/students",   # from your events file, re-test it
}
BLANK_EARLY = [   # dead early-careers page; the working careers_url is watched instead
    "Cisco", "Qualcomm", "American Express", "Visa", "Adobe",
    "NewSpace Research & Technologies", "Caterpillar",
]
BLANK_CAREERS = ["NXP Semiconductors"]          # dead careers_url; its Workday link is used
NEEDS_BROWSER = ["Electronic Arts (EA)", "Meta", "Teleperformance"]   # both URLs time out / block scripts

rows = list(csv.DictReader(open("companies.csv", encoding="utf-8")))
fields = list(rows[0].keys())
reset = []
for r in rows:
    c = r["company"]
    if c in NEW_EARLY:
        r["early_careers_url"] = NEW_EARLY[c]; reset.append(c)
    elif c in BLANK_EARLY:
        r["early_careers_url"] = ""
    elif c in BLANK_CAREERS:
        r["careers_url"] = ""
    elif c in NEEDS_BROWSER:
        r["check_method"] = "needs_browser"
    else:
        continue
    print("fixed:", c)

with open("companies.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)

try:   # re-baseline companies whose watched URL changed
    st = json.load(open("seen.json", encoding="utf-8"))
    for c in reset:
        st.get("page_watch", {}).pop(c, None)
    json.dump(st, open("seen.json", "w", encoding="utf-8"), indent=1)
except FileNotFoundError:
    pass
print("Done. Now run: python check_urls.py")
