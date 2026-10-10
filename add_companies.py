"""Appends 20 extra companies to YOUR companies.csv (keeps your edits, skips duplicates).
  python add_companies.py
URLs are best guesses: run `python check_urls.py` afterwards and fix any that fail."""
import csv

NEW = [  # company, sector, careers_url, early_careers_url
    ("Swiggy", "Consumer tech (India)", "https://careers.swiggy.com/", ""),
    ("Zomato", "Consumer tech (India)", "https://www.zomato.com/careers", ""),
    ("Meesho", "Consumer tech (India)", "https://www.meesho.io/jobs", ""),
    ("CRED", "Fintech (India)", "https://careers.cred.club/", ""),
    ("Groww", "Fintech (India)", "https://groww.in/careers", ""),
    ("Zoho", "Software (India)", "https://www.zoho.com/careers/", ""),
    ("Nvidia", "Semiconductors / AI", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite", "https://www.nvidia.com/en-us/about-nvidia/careers/university-recruiting/"),
    ("AMD", "Semiconductors", "https://careers.amd.com/", ""),
    ("Intel", "Semiconductors", "https://jobs.intel.com/", ""),
    ("Oracle", "Enterprise software", "https://careers.oracle.com/", ""),
    ("Databricks", "Data / AI", "https://www.databricks.com/company/careers", ""),
    ("Snowflake", "Data / cloud", "https://careers.snowflake.com/", ""),
    ("Nutanix", "Cloud infrastructure", "https://careers.nutanix.com/", ""),
    ("Airbnb", "Consumer tech", "https://careers.airbnb.com/", ""),
    ("Coinbase", "Fintech / crypto", "https://www.coinbase.com/careers", ""),
    ("MongoDB", "Data / software", "https://www.mongodb.com/careers", ""),
    ("DE Shaw", "Quant / trading", "https://www.deshaw.com/careers", ""),
    ("Optiver", "Quant / trading", "https://optiver.com/working-at-optiver/career-opportunities/", ""),
    ("WorldQuant", "Quant / trading", "https://www.worldquant.com/careers/", ""),
    ("Morgan Stanley", "Finance", "https://www.morganstanley.com/careers", ""),
]

with open("companies.csv", encoding="utf-8", newline="") as f:
    rd = csv.DictReader(f)
    fields, rows = rd.fieldnames, list(rd)
have = {r["company"].lower() for r in rows}

added = 0
for company, sector, url, early in NEW:
    if any(company.lower() in h or h in company.lower() for h in have):
        print("already there:", company)
        continue
    row = {k: "" for k in fields}
    row.update(company=company, sector=sector, careers_url=url, early_careers_url=early,
               ats_type="custom", check_method="page_watch", notes="added in bulk; URL unverified")
    rows.append(row)
    added += 1
    print("added:", company)

with open("companies.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print(f"Done: {added} added, {len(rows)} total. Next: python check_urls.py")
