"""Chart math that does not depend on HTTP."""

from datetime import datetime, time, timezone

import swisseph as swe

from app.models import BirthDetails
from app.services.kundali import format_dms, generate_kundali, locate_longitude, navamsa_sign_index


def _birth(moment: datetime, latitude: float = 0.0, longitude: float = 0.0) -> BirthDetails:
    utc_moment = moment.astimezone(timezone.utc)
    return BirthDetails(
        date_of_birth=utc_moment.date(),
        time_of_birth=time(utc_moment.hour, utc_moment.minute),
        place_of_birth="Test",
        resolved_name="Test",
        region="",
        country="",
        label="Test",
        latitude=latitude,
        longitude=longitude,
        timezone="UTC",
        local_datetime=utc_moment,
        utc_datetime=utc_moment,
    )


def test_longitude_placement_and_navamsa():
    opening = locate_longitude(0)
    assert opening.sign == "Aries"
    assert opening.nakshatra == "Ashwini"
    assert opening.pada == 1
    assert opening.nakshatra_lord == "Ketu"
    assert format_dms(10.5) == "10°30'00\""
    assert navamsa_sign_index(0) == 0
    assert navamsa_sign_index(10) == 3
    assert navamsa_sign_index(30) == 9


def test_known_sidereal_sun_signs_and_chart_structure():
    equinox = generate_kundali("equinox", _birth(datetime(2000, 3, 21, 12, tzinfo=timezone.utc)))
    assert equinox.sun_sign.sign == "Pisces"
    assert 23 < equinox.calculation.ayanamsa_degrees < 25

    august = generate_kundali(
        "august",
        _birth(datetime(1990, 8, 15, 5, tzinfo=timezone.utc), latitude=28.6139, longitude=77.2090),
    )
    assert august.sun_sign.sign == "Cancer"
    assert august.houses[0].sign == august.lagna.sign
    assert [planet.name for planet in august.planets] == [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Rahu",
        "Ketu",
    ]
    by_name = {planet.name: planet for planet in august.planets}
    separation = (by_name["Ketu"].longitude - by_name["Rahu"].longitude) % 360
    assert abs(separation - 180) < 0.001
    for planet in august.planets:
        assert planet.sign == august.houses[planet.house - 1].sign
        assert planet.name in august.houses[planet.house - 1].planets
    assert august.janma_nakshatra.name == august.moon_sign.nakshatra
    assert august.vimshottari.birth_mahadasha_lord == august.moon_sign.nakshatra_lord

    birth_utc = datetime(1990, 8, 15, 5, tzinfo=timezone.utc)
    at_birth = august.vimshottari.at_birth
    assert at_birth.mahadasha.start <= birth_utc < at_birth.mahadasha.end
    assert at_birth.antardasha.start <= birth_utc < at_birth.antardasha.end
    assert at_birth.pratyantardasha.start <= birth_utc < at_birth.pratyantardasha.end
    now = datetime.now(timezone.utc)
    current = august.vimshottari.current
    assert current is not None
    assert current.mahadasha.start <= now < current.mahadasha.end

    _cusps, angles = swe.houses(august.calculation.julian_day, 28.6139, 77.2090, b"P")
    expected = (angles[0] - august.calculation.ayanamsa_degrees) % 360
    delta = abs((expected - august.lagna.longitude + 180) % 360 - 180)
    assert delta < 0.02
