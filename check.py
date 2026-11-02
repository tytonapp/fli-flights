"""Run: python check.py  — tests fli directly, without the web UI."""
from datetime import date, timedelta
import fli
from fli.models import *
from fli.search import SearchFlights
try:
    from importlib.metadata import version; print("flights version:", version("flights"))
except Exception: pass
d = (date.today() + timedelta(days=21)).isoformat()
f = FlightSearchFilters(trip_type=TripType.ONE_WAY, passenger_info=PassengerInfo(adults=1),
    flight_segments=[FlightSegment(departure_airport=[[Airport.JFK, 0]],
                                   arrival_airport=[[Airport.LAX, 0]], travel_date=d)])
try:
    r = SearchFlights().search(f)
    print("results:", None if r is None else len(r))
    if r: print("first:", r[0].price, r[0].duration, r[0].stops)
except Exception as e:
    print("ERROR:", type(e).__name__, e)
