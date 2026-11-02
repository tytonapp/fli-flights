# fli-flights

A small web app for searching live Google Flights fares, built on [fli](https://github.com/punitarani/fli).

## Run

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

Then open http://localhost:5000.

`requirements.txt` installs `flights` from a pinned GitHub commit, so Git must be installed.

## Airport city names

Airport search matches city names and alternate names (Kochi/Cochin, Bengaluru/Bangalore) using
`airport_cities.json`, built from the public-domain [OurAirports](https://ourairports.com/data/) data.
To refresh it, download
[airports.csv](https://davidmegginson.github.io/ourairports-data/airports.csv) and run
`python build_cities.py airports.csv`.

## Troubleshooting

- `python check.py` runs one search directly through fli, without the web app.
- `python debug.py` prints Google's raw response, which is useful when searches return nothing.

fli is an unofficial client, and Google changes its format from time to time. If searches start failing,
look for a newer fli commit or release.
