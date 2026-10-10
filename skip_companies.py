"""Marks companies as skipped in companies.csv.
  python skip_companies.py "Electronic Arts" Teleperformance
Matches any part of the company name (case-insensitive) and prints what it changed."""
import csv, sys

terms = [t.lower() for t in sys.argv[1:]]
if not terms:
    sys.exit('Usage: python skip_companies.py "Company name" [another ...]')

with open("companies.csv", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

hits = 0
for r in rows:
    if any(t in r["company"].lower() for t in terms):
        print(f"skipped: {r['company']}  (was: {r['check_method']})")
        r["check_method"] = "skip"
        hits += 1

if hits == 0:
    print("No match. Company names in your file start with:")
    print(", ".join(r["company"][:18] for r in rows[:40]) + " ...")
else:
    with open("companies.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"Done: {hits} row(s) updated.")
