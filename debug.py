"""Run: python debug.py — shows what Google actually sends back to fli."""
from datetime import date, timedelta
from fli.models import *
from fli.search import SearchFlights
from fli.search._urls import with_locale_params

d = (date.today() + timedelta(days=30)).isoformat()
f = FlightSearchFilters(trip_type=TripType.ONE_WAY, passenger_info=PassengerInfo(adults=1),
    flight_segments=[FlightSegment(departure_airport=[[Airport.JFK, 0]],
                                   arrival_airport=[[Airport.LAX, 0]], travel_date=d)])
s = SearchFlights()
for name, cur, lang, ctry in [("default", None, None, None),
                              ("USD/en/US", "USD", "en-US", "US"),
                              ("INR/en/IN", "INR", "en-IN", "IN")]:
    url = with_locale_params(s.BASE_URL, cur, lang, ctry)
    r = s.client.post(url=url, data=f"f.req={f.encode()}", impersonate="chrome", allow_redirects=True)
    body = r.text
    print(f"\n== {name} ==")
    print("status:", r.status_code, "| final url:", getattr(r, "url", "?"))
    print("length:", len(body), "| has wrb.fr:", "wrb.fr" in body,
          "| mentions consent:", "consent" in body.lower())
    print("start:", body[:300].replace("\n", " "))
    try:
        res = s.search(f, currency=cur, language=lang, country=ctry)
        print("fli results:", None if res is None else len(res))
    except Exception as e:
        print("fli error:", type(e).__name__, e)
