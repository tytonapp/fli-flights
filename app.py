"""Flight search UI backed by punitarani/fli (pip package: `flights`).
Run:  pip install -r requirements.txt && python app.py  ->  http://localhost:5000
"""
import json
import re
from datetime import date
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError
from fli.models import (Airport, FlightSearchFilters, FlightSegment, MaxStops,
                        PassengerInfo, SeatType, SortBy, TripType)
from fli.search import SearchFlights
from fli.search._urls import with_locale_params
from fli.search.exceptions import (SearchConnectionError, SearchHTTPError,
                                   SearchTimeoutError)
from fli.search.flights import SearchParseError

app = Flask(__name__, static_folder="static")

# {code: [city, country, aliases]} from OurAirports; rebuild with build_cities.py
CITIES_FILE = Path(__file__).with_name("airport_cities.json")
CITIES = json.loads(CITIES_FILE.read_text(encoding="utf-8")) if CITIES_FILE.exists() else {}

SEATS = {"economy": SeatType.ECONOMY, "premium": SeatType.PREMIUM_ECONOMY,
         "business": SeatType.BUSINESS, "first": SeatType.FIRST}
STOPS = {"any": MaxStops.ANY, "0": MaxStops.NON_STOP,
         "1": MaxStops.ONE_STOP_OR_FEWER, "2": MaxStops.TWO_OR_FEWER_STOPS}
SORTS = {"best": SortBy.TOP_FLIGHTS, "price": SortBy.CHEAPEST,
         "duration": SortBy.DURATION, "departure": SortBy.DEPARTURE_TIME}


def code(e):  # enum member -> IATA code
    return getattr(e, "name", str(e)).lstrip("_")


def label(e):  # enum member -> readable name
    return str(getattr(e, "value", e))


def leg_dict(l):
    return {"airline": label(l.airline), "airline_code": code(l.airline),
            "flight_number": l.flight_number,
            "from": code(l.departure_airport), "to": code(l.arrival_airport),
            "depart": l.departure_datetime.isoformat(),
            "arrive": l.arrival_datetime.isoformat(),
            "duration": getattr(l, "duration", None)}


def flight_dict(f):
    legs = [leg_dict(l) for l in f.legs]
    return {"price": f.price, "duration": f.duration, "stops": f.stops, "legs": legs}


GRPC = {13: "internal error", 14: "service unavailable", 8: "resource exhausted",
        3: "invalid argument", 7: "permission denied"}


def upstream_code(body):
    """Return the gRPC error code if Google's reply is an error envelope, else None."""
    m = re.search(r'"wrb\.fr",null,null,null,null,\[(\d+)\]', body or "")
    return int(m.group(1)) if m else None


def upstream_message(code):
    return (f"Google returned an {GRPC.get(code, 'error')} ({code}) instead of fares. "
            "This is a Google-side problem, not your search. Try again later.")


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/airports")
def airports():
    out = []
    for a in Airport:
        c = code(a)
        city, country, aka = CITIES.get(c, ("", "", ""))
        out.append({"code": c, "name": label(a), "city": city, "country": country, "aka": aka})
    resp = jsonify(out)
    resp.cache_control.public, resp.cache_control.max_age = True, 86400
    return resp


class BadRequest(ValueError):
    pass


def parse_date(q, key, required=True):
    v = q.get(key)
    if not v:
        if required:
            raise BadRequest("Please choose a departure date.")
        return None
    try:
        d = date.fromisoformat(v)
    except (TypeError, ValueError):
        raise BadRequest(f"Invalid date: {v!r}.")
    if d < date.today():
        raise BadRequest("Dates can't be in the past.")
    return d


def parse_int(q, key, default, lo, hi, what):
    v = q.get(key)
    try:
        n = default if v in (None, "") else int(v)
    except (TypeError, ValueError):
        raise BadRequest(f"{what} must be a number.")
    if not lo <= n <= hi:
        raise BadRequest(f"{what} must be between {lo} and {hi}.")
    return n


def build_filters(q):
    try:
        o = Airport[str(q.get("origin", "")).strip().upper()]
        d = Airport[str(q.get("destination", "")).strip().upper()]
    except KeyError:
        raise BadRequest("Unknown airport code. Pick one from the suggestions.")
    if o == d:
        raise BadRequest("Origin and destination must be different.")
    dep = parse_date(q, "depart_date")
    ret = parse_date(q, "return_date", required=False)
    if ret and ret < dep:
        raise BadRequest("Return date must be on or after the departure date.")
    adults = parse_int(q, "adults", 1, 1, 9, "Adults")
    children = parse_int(q, "children", 0, 0, 8, "Children")
    if adults + children > 9:
        raise BadRequest("Google Flights allows at most 9 passengers.")
    segs = [FlightSegment(departure_airport=[[o, 0]], arrival_airport=[[d, 0]],
                          travel_date=dep.isoformat())]
    if ret:
        segs.append(FlightSegment(departure_airport=[[d, 0]], arrival_airport=[[o, 0]],
                                  travel_date=ret.isoformat()))
    return FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP if ret else TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=adults, children=children),
        flight_segments=segs,
        seat_type=SEATS.get(q.get("seat", "economy"), SeatType.ECONOMY),
        stops=STOPS.get(str(q.get("stops", "any")), MaxStops.ANY),
        sort_by=SORTS.get(q.get("sort", "best"), SortBy.TOP_FLIGHTS),
    ), bool(ret)


@app.post("/api/search")
def search():
    q = request.get_json(silent=True)
    if not isinstance(q, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    try:
        filters, round_trip = build_filters(q)
    except BadRequest as e:
        return jsonify(error=str(e)), 400
    except ValidationError as e:
        msg = "; ".join(err.get("msg", "") for err in e.errors()) or str(e)
        return jsonify(error=f"Invalid search: {msg}"), 400
    cur = (q.get("currency") or "").upper() or None
    s = SearchFlights()
    try:
        results = s.search(filters, currency=cur) or []
    except SearchTimeoutError:
        return jsonify(error="Google Flights took too long to respond. Try again."), 504
    except SearchConnectionError:
        return jsonify(error="Couldn't reach Google Flights. Check your internet connection."), 502
    except SearchHTTPError as e:
        app.logger.warning("Google HTTP error %s: %s", e.status_code, e)
        status = f" (HTTP {e.status_code})" if e.status_code else ""
        return jsonify(error=f"Google Flights returned an error{status}. Try again later."), 502
    except SearchParseError as e:
        app.logger.exception("fli could not parse Google's reply")
        return jsonify(error="Google's reply format has changed and fli can't read it. "
                             f"Try updating the 'flights' package. ({e})"), 502
    except Exception as e:  # anything else from fli / curl_cffi
        app.logger.exception("fli search failed")
        return jsonify(error=f"Search failed ({type(e).__name__}): {e}"), 502
    app.logger.info("fli returned %d results", len(results))
    if not results:  # empty: real "no flights" or a hidden Google error? Check.
        try:  # repeat the exact same request (same currency) and inspect the raw reply
            body = s.client.post(url=with_locale_params(s.BASE_URL, cur, None, None),
                                 data=f"f.req={filters.encode()}",
                                 impersonate="chrome", allow_redirects=True).text
            code_ = upstream_code(body)
            if code_ not in (None, 0):
                app.logger.warning("Google error envelope: %s", code_)
                return jsonify(error=upstream_message(code_), code=code_), 502
        except Exception:
            app.logger.exception("error-envelope probe failed")
    out = []
    for r in results:
        if isinstance(r, (tuple, list)):  # round trip: (outbound, return)
            out_f, ret_f = r[0], r[1] if len(r) > 1 else None
            item = flight_dict(out_f)
            if ret_f is not None:
                item["return"] = flight_dict(ret_f)
                item["price"] = ret_f.price if ret_f.price is not None else out_f.price  # total fare
            out.append(item)
        else:
            out.append(flight_dict(r))
    return jsonify(results=out, round_trip=round_trip)


if __name__ == "__main__":
    app.run(debug=True)
