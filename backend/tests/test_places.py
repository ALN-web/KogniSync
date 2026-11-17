import pytest

from app.data.cities import UnknownPlaceError, resolve_place
from app.domain.models import Place, PlaceKind


@pytest.mark.parametrize(
    "text, name, city",
    [
        ("Udayapalya, Bengaluru", "Udayapalya", "BLR"),
        ("CP Delhi", "Connaught Place", "DEL"),
        ("cp", "Connaught Place", "DEL"),
        ("Bangalore", "Bengaluru", "BLR"),
        ("HITEC City", "HITEC City", "HYD"),
        ("Gurgaon", "Cyber City Gurugram", "DEL"),
    ],
)
def test_resolves_common_names(text, name, city):
    place = resolve_place(text)
    assert place.name == name
    assert place.city == city


def test_resolves_airport_code():
    place = resolve_place("BLR")
    assert place.kind == PlaceKind.AIRPORT
    assert place.city == "BLR"


def test_coordinates_get_city_assigned():
    place = resolve_place(Place(name="Home", lat=12.93, lon=77.62))
    assert place.city == "BLR"


def test_outside_coverage_is_rejected():
    with pytest.raises(UnknownPlaceError):
        resolve_place(Place(name="Leh", lat=34.15, lon=77.58))
    with pytest.raises(UnknownPlaceError):
        resolve_place("Atlantis")


def test_hubs_endpoint(client):
    hubs = client.get("/api/v1/hubs").json()["hubs"]
    assert len(hubs) == 14
    blr = next(h for h in hubs if h["key"] == "BLR")
    assert blr["name"] == "Bengaluru" and blr["has_metro"] is True
    assert all(6 < h["lat"] < 36 and 68 < h["lon"] < 98 for h in hubs)
