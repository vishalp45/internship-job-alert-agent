"""Changes check_method in companies.csv (default: skip).
  python skip_companies.py "Electronic Arts" Teleperformance
  python skip_companies.py --method api Palantir Workday NXP Unisys
Matches any part of the company name (case-insensitive) and prints what it changed."""
import csv, sys

args = sys.argv[1:]
method = "skip"
if args[:1] == ["--method"] and len(args) >= 2:
    method, args = args[1], args[2:]
terms = [t.lower() for t in args]
if not terms:
    sys.exit('Usage: python skip_companies.py [--method api|page_watch|skip] "Company name" [another ...]')

with open("companies.csv", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

hits = 0
for r in rows:
    if any(t in r["company"].lower() for t in terms):
        print(f"{method}: {r['company']}  (was: {r['check_method']})")
        r["check_method"] = method
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
