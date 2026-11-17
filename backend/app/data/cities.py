"""The 14 Indian metro hubs modeled in the MVP, plus a small gazetteer of localities.

Coordinates are approximate and only used by the mock providers. A real geocoder (Google
Places / Geocoding API) replaces ``resolve_place`` when live providers are wired in.
"""

from dataclasses import dataclass, field

from app.domain.geo import haversine_km
from app.domain.models import Place, PlaceKind


@dataclass(frozen=True)
class City:
    key: str
    name: str
    center: tuple[float, float]
    airport: tuple[str, str, float, float]  # code, name, lat, lon
    station: tuple[str, str, float, float]
    bus_terminal: tuple[str, float, float]
    metro: str | None  # operator name, None if the city has no metro
    city_bus: str
    airport_bus: str | None = None
    localities: dict[str, tuple[float, float]] = field(default_factory=dict)

    def center_place(self) -> Place:
        return Place(name=self.name, lat=self.center[0], lon=self.center[1], city=self.key)

    def airport_place(self) -> Place:
        code, name, lat, lon = self.airport
        return Place(name=name, lat=lat, lon=lon, city=self.key, kind=PlaceKind.AIRPORT, code=code)

    def station_place(self) -> Place:
        code, name, lat, lon = self.station
        return Place(name=name, lat=lat, lon=lon, city=self.key, kind=PlaceKind.STATION, code=code)

    def bus_terminal_place(self) -> Place:
        name, lat, lon = self.bus_terminal
        return Place(name=name, lat=lat, lon=lon, city=self.key, kind=PlaceKind.BUS_TERMINAL)


CITIES: dict[str, City] = {
    c.key: c
    for c in [
        City(
            "BLR",
            "Bengaluru",
            (12.9716, 77.5946),
            ("BLR", "Kempegowda International Airport", 13.1986, 77.7066),
            ("SBC", "KSR Bengaluru City Junction", 12.9781, 77.5695),
            ("Kempegowda Bus Station (Majestic)", 12.9774, 77.5713),
            "Namma Metro",
            "BMTC",
            "BMTC Vayu Vajra",
            {
                "Udayapalya": (12.8902, 77.5600),
                "Koramangala": (12.9352, 77.6245),
                "Indiranagar": (12.9784, 77.6408),
                "Whitefield": (12.9698, 77.7500),
                "Electronic City": (12.8452, 77.6602),
                "HSR Layout": (12.9116, 77.6474),
                "Jayanagar": (12.9250, 77.5938),
                "MG Road": (12.9756, 77.6050),
            },
        ),
        City(
            "DEL",
            "Delhi NCR",
            (28.6315, 77.2167),
            ("DEL", "Indira Gandhi International Airport", 28.5562, 77.1000),
            ("NDLS", "New Delhi Railway Station", 28.6430, 77.2194),
            ("ISBT Kashmere Gate", 28.6675, 77.2283),
            "Delhi Metro (DMRC)",
            "DTC",
            "DTC Airport Express",
            {
                "Connaught Place": (28.6315, 77.2167),
                "Cyber City Gurugram": (28.4950, 77.0890),
                "Noida Sector 18": (28.5708, 77.3260),
                "Saket": (28.5245, 77.2066),
                "Karol Bagh": (28.6519, 77.1909),
                "Dwarka": (28.5921, 77.0460),
            },
        ),
        City(
            "BOM",
            "Mumbai",
            (19.0760, 72.8777),
            ("BOM", "Chhatrapati Shivaji Maharaj International Airport", 19.0896, 72.8656),
            ("CSMT", "Chhatrapati Shivaji Maharaj Terminus", 18.9402, 72.8355),
            ("Mumbai Central Bus Depot", 18.9690, 72.8205),
            "Mumbai Metro",
            "BEST",
            None,
            {
                "Andheri": (19.1136, 72.8697),
                "Bandra": (19.0596, 72.8295),
                "Powai": (19.1176, 72.9060),
                "Lower Parel": (18.9986, 72.8302),
                "Colaba": (18.9067, 72.8147),
            },
        ),
        City(
            "HYD",
            "Hyderabad",
            (17.3850, 78.4867),
            ("HYD", "Rajiv Gandhi International Airport", 17.2403, 78.4294),
            ("SC", "Secunderabad Junction", 17.4337, 78.5016),
            ("Mahatma Gandhi Bus Station", 17.3780, 78.4840),
            "Hyderabad Metro",
            "TGSRTC City",
            "TGSRTC Pushpak",
            {
                "HITEC City": (17.4435, 78.3772),
                "Gachibowli": (17.4401, 78.3489),
                "Banjara Hills": (17.4156, 78.4347),
            },
        ),
        City(
            "MAA",
            "Chennai",
            (13.0827, 80.2707),
            ("MAA", "Chennai International Airport", 12.9941, 80.1709),
            ("MAS", "Chennai Central", 13.0827, 80.2757),
            ("CMBT Koyambedu", 13.0694, 80.2052),
            "Chennai Metro",
            "MTC",
            None,
            {
                "T Nagar": (13.0418, 80.2341),
                "Adyar": (13.0012, 80.2565),
                "OMR Sholinganallur": (12.9010, 80.2279),
            },
        ),
        City(
            "PNQ",
            "Pune",
            (18.5204, 73.8567),
            ("PNQ", "Pune Airport", 18.5822, 73.9197),
            ("PUNE", "Pune Junction", 18.5289, 73.8744),
            ("Swargate Bus Stand", 18.5018, 73.8636),
            "Pune Metro",
            "PMPML",
            None,
            {
                "Hinjewadi": (18.5912, 73.7389),
                "Koregaon Park": (18.5362, 73.8940),
                "Kothrud": (18.5074, 73.8077),
            },
        ),
        City(
            "CCU",
            "Kolkata",
            (22.5726, 88.3639),
            ("CCU", "Netaji Subhas Chandra Bose International Airport", 22.6547, 88.4467),
            ("HWH", "Howrah Junction", 22.5838, 88.3426),
            ("Esplanade Bus Terminus", 22.5646, 88.3510),
            "Kolkata Metro",
            "WBTC",
            None,
            {"Salt Lake Sector V": (22.5726, 88.4339), "Park Street": (22.5530, 88.3520)},
        ),
        City(
            "AMD",
            "Ahmedabad",
            (23.0225, 72.5714),
            ("AMD", "Sardar Vallabhbhai Patel International Airport", 23.0772, 72.6347),
            ("ADI", "Ahmedabad Junction", 23.0258, 72.6010),
            ("Geeta Mandir Bus Station", 23.0145, 72.5900),
            "Ahmedabad Metro",
            "AMTS",
            None,
            {"SG Highway": (23.0300, 72.5070), "Navrangpura": (23.0365, 72.5611)},
        ),
        City(
            "JAI",
            "Jaipur",
            (26.9124, 75.7873),
            ("JAI", "Jaipur International Airport", 26.8242, 75.8122),
            ("JP", "Jaipur Junction", 26.9196, 75.7878),
            ("Sindhi Camp Bus Stand", 26.9230, 75.7990),
            "Jaipur Metro",
            "JCTSL",
            None,
            {"Malviya Nagar Jaipur": (26.8530, 75.8050)},
        ),
        City(
            "COK",
            "Kochi",
            (9.9312, 76.2673),
            ("COK", "Cochin International Airport", 10.1520, 76.4019),
            ("ERS", "Ernakulam Junction", 9.9690, 76.2910),
            ("Vyttila Mobility Hub", 9.9672, 76.3204),
            "Kochi Metro",
            "KSRTC City",
            None,
            {"Kakkanad": (10.0159, 76.3419), "Fort Kochi": (9.9658, 76.2421)},
        ),
        City(
            "LKO",
            "Lucknow",
            (26.8467, 80.9462),
            ("LKO", "Chaudhary Charan Singh International Airport", 26.7606, 80.8893),
            ("LKO", "Lucknow Charbagh", 26.8318, 80.9220),
            ("Alambagh Bus Terminal", 26.8139, 80.9020),
            "Lucknow Metro",
            "LCTSL",
            None,
            {"Gomti Nagar": (26.8500, 81.0000), "Hazratganj": (26.8530, 80.9460)},
        ),
        City(
            "IXC",
            "Chandigarh",
            (30.7333, 76.7794),
            ("IXC", "Chandigarh International Airport", 30.6735, 76.7885),
            ("CDG", "Chandigarh Railway Station", 30.7024, 76.8221),
            ("ISBT Sector 43", 30.7186, 76.7520),
            None,
            "CTU",
            None,
            {"Sector 17": (30.7398, 76.7827)},
        ),
        City(
            "GOI",
            "Goa",
            (15.4909, 73.8278),
            ("GOI", "Goa International Airport (Dabolim)", 15.3808, 73.8314),
            ("MAO", "Madgaon Junction", 15.2665, 73.9706),
            ("Kadamba Bus Stand Panaji", 15.4960, 73.8350),
            None,
            "KTC",
            None,
            {"Panaji": (15.4909, 73.8278), "Calangute": (15.5439, 73.7553)},
        ),
        City(
            "BBI",
            "Bhubaneswar",
            (20.2961, 85.8245),
            ("BBI", "Biju Patnaik International Airport", 20.2444, 85.8178),
            ("BBS", "Bhubaneswar Railway Station", 20.2667, 85.8433),
            ("Baramunda Bus Stand", 20.2860, 85.8000),
            None,
            "Mo Bus",
            None,
            {"Patia": (20.3530, 85.8190)},
        ),
    ]
}

# Common short names people type or say.
ALIASES: dict[str, str] = {
    "cp": "Connaught Place",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "delhi": "Connaught Place",
    "new delhi": "Connaught Place",
    "gurgaon": "Cyber City Gurugram",
    "gurugram": "Cyber City Gurugram",
    "noida": "Noida Sector 18",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "ecity": "Electronic City",
    "hitech city": "HITEC City",
}

COVERAGE_RADIUS_KM = 60.0


class UnknownPlaceError(ValueError):
    pass


def nearest_city(lat: float, lon: float) -> City | None:
    best, best_d = None, COVERAGE_RADIUS_KM
    for city in CITIES.values():
        d = haversine_km(lat, lon, *city.center)
        if d <= best_d:
            best, best_d = city, d
    return best


def _index() -> dict[str, Place]:
    idx: dict[str, Place] = {}
    for city in CITIES.values():
        idx[city.name.lower()] = city.center_place()
        for name, (lat, lon) in city.localities.items():
            idx[name.lower()] = Place(name=name, lat=lat, lon=lon, city=city.key)
        for place in (city.airport_place(), city.station_place(), city.bus_terminal_place()):
            idx[place.name.lower()] = place
            if place.code:
                idx.setdefault(place.code.lower(), place)
    return idx


_INDEX = _index()


def resolve_place(value: str | Place) -> Place:
    """Turn user input into a Place inside one of the covered cities."""
    if isinstance(value, Place):
        city = nearest_city(value.lat, value.lon)
        if city is None:
            raise UnknownPlaceError(f"{value.name} is outside the 14 covered cities")
        return value.model_copy(update={"city": city.key})

    text = " ".join(value.lower().replace(",", " ").split())
    if not text:
        raise UnknownPlaceError("empty place")
    text = ALIASES.get(text, text)
    text = text.lower()
    if text in _INDEX:
        return _INDEX[text]
    # "Udayapalya Bengaluru": a specific place named in the text beats the city name.
    city_names = {n.lower() for n in _city_names()}
    # Short keys (airport codes like "del") only match exactly, never as substrings.
    matches = [
        name
        for name in _INDEX
        if len(name) >= 5 and (name in text or (len(text) >= 4 and text in name))
    ]
    specific = [m for m in matches if m not in city_names]
    if specific:
        return _INDEX[max(specific, key=len)]
    # "CP Delhi": a known short name.
    for word in text.split():
        if word in ALIASES:
            return _INDEX[ALIASES[word].lower()]
    if matches:
        return _INDEX[max(matches, key=len)]
    raise UnknownPlaceError(f"Could not find '{value}' in the covered cities")


def _city_names() -> set[str]:
    return {c.name for c in CITIES.values()}


def known_place_names() -> list[str]:
    return sorted({p.name for p in _INDEX.values()})
