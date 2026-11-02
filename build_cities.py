"""Run: python build_cities.py airports.csv  — rebuilds airport_cities.json.

airports.csv is the public-domain OurAirports dataset:
https://davidmegginson.github.io/ourairports-data/airports.csv
Only airports that fli knows are kept, as {code: [city, country, aliases]}.
"""
import csv, json, sys
from fli.models import Airport

EXTRA = {"GOI": "Goa", "GOX": "Goa", "TRV": "Trivandrum"}  # well-known names the dataset lacks
SKIP = ("air force", "air base", "airport", "airfield", "station", "military")

codes = {a.name.lstrip("_") for a in Airport}
rows = {}
with open(sys.argv[1], encoding="utf-8") as f:
    for r in csv.DictReader(f):
        c = r["iata_code"].strip()
        if c in codes and (c not in rows or r["scheduled_service"] == "yes"):
            rows[c] = r

out = {}
for c, r in sorted(rows.items()):
    city = r["municipality"].strip()
    aliases = [k.strip() for k in r["keywords"].split(",")
               if k.strip() and k.strip() != c and not any(s in k.lower() for s in SKIP)]
    if c in EXTRA:
        aliases.append(EXTRA[c])
    aliases = [a for a in dict.fromkeys(aliases) if a.lower() != city.lower()][:4]
    out[c] = [city, r["iso_country"], ", ".join(aliases)]

with open("airport_cities.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"wrote airport_cities.json: {len(out)} of {len(codes)} airports")
