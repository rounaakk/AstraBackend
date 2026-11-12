"""Sidereal Lahiri kundali from a birth instant."""

import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import swisseph as swe

from app.errors import ChartCalculationError
from app.models import BirthDetails
from app.presenters import birth_details_out
from app.schemas.kundali import (
    CalculationOut,
    ChartPointOut,
    CurrentDashaOut,
    DashaBalanceOut,
    DashaSliceOut,
    HouseOut,
    JanmaNakshatraOut,
    KundaliOut,
    MahadashaOut,
    ManglikOut,
    PlanetOut,
    VimshottariOut,
    YogaOut,
)

logger = logging.getLogger(__name__)

YEAR_DAYS = 365.2425
NAKSHATRA_SPAN = 360 / 27
KENDRA = {1, 4, 7, 10}
MANGLIK_HOUSES = {1, 2, 4, 7, 8, 12}
DASHA_SEQUENCE = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
DASHA_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
}
SANSKRIT = {
    "Sun": "Surya",
    "Moon": "Chandra",
    "Mars": "Mangal",
    "Mercury": "Budha",
    "Jupiter": "Guru",
    "Venus": "Shukra",
    "Saturn": "Shani",
    "Rahu": "Rahu",
    "Ketu": "Ketu",
}
HOUSE_THEMES = (
    "Identity",
    "Wealth",
    "Siblings",
    "Home",
    "Children",
    "Health",
    "Marriage",
    "Longevity",
    "Dharma",
    "Career",
    "Gains",
    "Expenses",
)
ELEMENT_START = {"fire": 0, "earth": 9, "air": 6, "water": 3}
EXALTATION = {
    "Sun": "Aries",
    "Moon": "Taurus",
    "Mars": "Capricorn",
    "Mercury": "Virgo",
    "Jupiter": "Cancer",
    "Venus": "Pisces",
    "Saturn": "Libra",
}
DEBILITATION = {
    "Sun": "Libra",
    "Moon": "Scorpio",
    "Mars": "Cancer",
    "Mercury": "Pisces",
    "Jupiter": "Capricorn",
    "Venus": "Virgo",
    "Saturn": "Aries",
}
OWN_SIGNS = {
    "Sun": {"Leo"},
    "Moon": {"Cancer"},
    "Mars": {"Aries", "Scorpio"},
    "Mercury": {"Gemini", "Virgo"},
    "Jupiter": {"Sagittarius", "Pisces"},
    "Venus": {"Taurus", "Libra"},
    "Saturn": {"Capricorn", "Aquarius"},
}
COMBUST_ORB = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": 14.0,
    "Jupiter": 11.0,
    "Venus": 10.0,
    "Saturn": 15.0,
}

_calc_lock = threading.Lock()


@dataclass(frozen=True)
class SignInfo:
    name: str
    sanskrit: str
    element: str
    modality: str
    lord: str


@dataclass(frozen=True)
class NakshatraInfo:
    name: str
    lord: str
    deity: str


SIGNS = (
    SignInfo("Aries", "Mesha", "fire", "movable", "Mars"),
    SignInfo("Taurus", "Vrishabha", "earth", "fixed", "Venus"),
    SignInfo("Gemini", "Mithuna", "air", "dual", "Mercury"),
    SignInfo("Cancer", "Karka", "water", "movable", "Moon"),
    SignInfo("Leo", "Simha", "fire", "fixed", "Sun"),
    SignInfo("Virgo", "Kanya", "earth", "dual", "Mercury"),
    SignInfo("Libra", "Tula", "air", "movable", "Venus"),
    SignInfo("Scorpio", "Vrishchika", "water", "fixed", "Mars"),
    SignInfo("Sagittarius", "Dhanu", "fire", "dual", "Jupiter"),
    SignInfo("Capricorn", "Makara", "earth", "movable", "Saturn"),
    SignInfo("Aquarius", "Kumbha", "air", "fixed", "Saturn"),
    SignInfo("Pisces", "Meena", "water", "dual", "Jupiter"),
)

NAKSHATRAS = (
    NakshatraInfo("Ashwini", "Ketu", "Ashwini Kumaras"),
    NakshatraInfo("Bharani", "Venus", "Yama"),
    NakshatraInfo("Krittika", "Sun", "Agni"),
    NakshatraInfo("Rohini", "Moon", "Brahma"),
    NakshatraInfo("Mrigashira", "Mars", "Soma"),
    NakshatraInfo("Ardra", "Rahu", "Rudra"),
    NakshatraInfo("Punarvasu", "Jupiter", "Aditi"),
    NakshatraInfo("Pushya", "Saturn", "Brihaspati"),
    NakshatraInfo("Ashlesha", "Mercury", "Nagas"),
    NakshatraInfo("Magha", "Ketu", "Pitris"),
    NakshatraInfo("Purva Phalguni", "Venus", "Bhaga"),
    NakshatraInfo("Uttara Phalguni", "Sun", "Aryaman"),
    NakshatraInfo("Hasta", "Moon", "Savitar"),
    NakshatraInfo("Chitra", "Mars", "Tvashtar"),
    NakshatraInfo("Swati", "Rahu", "Vayu"),
    NakshatraInfo("Vishakha", "Jupiter", "Indra-Agni"),
    NakshatraInfo("Anuradha", "Saturn", "Mitra"),
    NakshatraInfo("Jyeshtha", "Mercury", "Indra"),
    NakshatraInfo("Mula", "Ketu", "Nirriti"),
    NakshatraInfo("Purva Ashadha", "Venus", "Apah"),
    NakshatraInfo("Uttara Ashadha", "Sun", "Vishvedevas"),
    NakshatraInfo("Shravana", "Moon", "Vishnu"),
    NakshatraInfo("Dhanishta", "Mars", "Vasus"),
    NakshatraInfo("Shatabhisha", "Rahu", "Varuna"),
    NakshatraInfo("Purva Bhadrapada", "Jupiter", "Aja Ekapada"),
    NakshatraInfo("Uttara Bhadrapada", "Saturn", "Ahirbudhnya"),
    NakshatraInfo("Revati", "Mercury", "Pushan"),
)


def _validate_tables() -> None:
    if len(SIGNS) != 12 or len(NAKSHATRAS) != 27 or sum(DASHA_YEARS.values()) != 120:
        raise RuntimeError("Astrology reference tables are incomplete")
    for index, nakshatra in enumerate(NAKSHATRAS):
        if nakshatra.lord != DASHA_SEQUENCE[index % 9]:
            raise RuntimeError(f"Nakshatra lord mismatch for {nakshatra.name}")


_validate_tables()


@dataclass(frozen=True)
class Placement:
    longitude: float
    sign: str
    sign_sanskrit: str
    sign_number: int
    sign_lord: str
    element: str
    modality: str
    degree_in_sign: float
    dms: str
    nakshatra: str
    pada: int
    nakshatra_lord: str
    nakshatra_deity: str
    navamsa_sign: str
    navamsa_sign_sanskrit: str


def format_dms(degree_in_sign: float) -> str:
    total_seconds = int(round(degree_in_sign * 3600))
    total_seconds = min(max(total_seconds, 0), 30 * 3600 - 1)
    degrees, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{degrees}\u00b0{minutes:02d}'{seconds:02d}\""


def navamsa_sign_index(longitude: float) -> int:
    longitude = longitude % 360
    sign_index = int(longitude // 30) % 12
    degree = longitude - sign_index * 30
    pada = int(degree * 9 // 30)
    pada = min(max(pada, 0), 8)
    return (ELEMENT_START[SIGNS[sign_index].element] + pada) % 12


def locate_longitude(longitude: float) -> Placement:
    longitude = longitude % 360
    sign_index = int(longitude // 30) % 12
    degree = longitude - sign_index * 30
    if degree >= 30:
        degree = 29.9999
    sign = SIGNS[sign_index]
    nakshatra_index = int(longitude / NAKSHATRA_SPAN)
    if nakshatra_index > 26:
        nakshatra_index = 26
    nakshatra = NAKSHATRAS[nakshatra_index]
    position_in_nakshatra = longitude - nakshatra_index * NAKSHATRA_SPAN
    pada = int(position_in_nakshatra / (NAKSHATRA_SPAN / 4)) + 1
    pada = min(max(pada, 1), 4)
    navamsa = SIGNS[navamsa_sign_index(longitude)]
    return Placement(
        longitude=round(longitude, 6),
        sign=sign.name,
        sign_sanskrit=sign.sanskrit,
        sign_number=sign_index + 1,
        sign_lord=sign.lord,
        element=sign.element,
        modality=sign.modality,
        degree_in_sign=round(degree, 4),
        dms=format_dms(degree),
        nakshatra=nakshatra.name,
        pada=pada,
        nakshatra_lord=nakshatra.lord,
        nakshatra_deity=nakshatra.deity,
        navamsa_sign=navamsa.name,
        navamsa_sign_sanskrit=navamsa.sanskrit,
    )


def generate_kundali(user_id: str, birth: BirthDetails) -> KundaliOut:
    try:
        julian_day, ayanamsa, ascendant, raw_planets = _raw_positions(birth)
    except ChartCalculationError:
        raise
    except Exception as exc:
        logger.exception("Kundali calculation failed")
        raise ChartCalculationError("Could not compute the kundali for this birth time and place") from exc
    return _assemble(user_id, birth, julian_day, ayanamsa, ascendant, raw_planets)


def _raw_positions(birth: BirthDetails) -> tuple[float, float, float, dict[str, tuple[float, float]]]:
    with _calc_lock:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        julian_day = _julian_day(birth.utc_datetime)
        ayanamsa = float(swe.get_ayanamsa_ut(julian_day))
        ascendant = _sidereal_ascendant(julian_day, birth.latitude, birth.longitude, ayanamsa)
        planet_ids = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mars": swe.MARS,
            "Mercury": swe.MERCURY,
            "Jupiter": swe.JUPITER,
            "Venus": swe.VENUS,
            "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE,
        }
        positions = {name: _planet(julian_day, planet_id) for name, planet_id in planet_ids.items()}
        rahu_longitude, rahu_speed = positions["Rahu"]
        positions["Ketu"] = ((rahu_longitude + 180.0) % 360.0, rahu_speed)
        return julian_day, ayanamsa, ascendant, positions


def _julian_day(moment: datetime) -> float:
    moment = moment.astimezone(timezone.utc)
    hour = moment.hour + moment.minute / 60 + moment.second / 3600 + moment.microsecond / 3_600_000_000
    calendar = getattr(swe, "GREG_CAL", 1)
    return float(swe.julday(moment.year, moment.month, moment.day, hour, calendar))


def _planet(julian_day: float, planet_id: int) -> tuple[float, float]:
    flags = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    result = swe.calc_ut(julian_day, planet_id, flags)
    values = result[0] if isinstance(result[0], tuple) else result
    return float(values[0]) % 360.0, float(values[3])


def _sidereal_ascendant(julian_day: float, latitude: float, longitude: float, ayanamsa: float) -> float:
    last_error: Exception | None = None
    for system in (b"P", b"E", b"W", b"O"):
        try:
            _cusps, angles = swe.houses(julian_day, latitude, longitude, system)
            return (float(angles[0]) - ayanamsa) % 360.0
        except Exception as exc:
            last_error = exc
    raise ChartCalculationError("Could not compute the ascendant for this birth place") from last_error


def _assemble(
    user_id: str,
    birth: BirthDetails,
    julian_day: float,
    ayanamsa: float,
    ascendant_longitude: float,
    raw_planets: dict[str, tuple[float, float]],
) -> KundaliOut:
    lagna = locate_longitude(ascendant_longitude)
    order = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
    sun_longitude = raw_planets["Sun"][0]
    planets: list[PlanetOut] = []
    for name in order:
        longitude, speed = raw_planets[name]
        placement = locate_longitude(longitude)
        dignity = _dignity(name, placement.sign)
        retrograde = False if name in {"Sun", "Moon"} else speed < 0
        combust = _is_combust(name, longitude, sun_longitude, retrograde)
        planets.append(
            PlanetOut(
                name=name,
                sanskrit=SANSKRIT[name],
                house=_house_number(placement.sign_number, lagna.sign_number),
                retrograde=retrograde,
                combust=combust,
                dignity=dignity,
                **asdict(placement),
            )
        )

    houses = []
    for offset, theme in enumerate(HOUSE_THEMES):
        sign = SIGNS[(lagna.sign_number - 1 + offset) % 12]
        number = offset + 1
        houses.append(
            HouseOut(
                number=number,
                sign=sign.name,
                sign_sanskrit=sign.sanskrit,
                sign_number=(lagna.sign_number - 1 + offset) % 12 + 1,
                sign_lord=sign.lord,
                theme=theme,
                planets=[planet.name for planet in planets if planet.house == number],
            )
        )

    by_name = {planet.name: planet for planet in planets}
    moon = by_name["Moon"]
    vimshottari = _vimshottari(birth.utc_datetime, raw_planets["Moon"][0])
    return KundaliOut(
        id=str(uuid4()),
        user_id=user_id,
        generated_at=datetime.now(timezone.utc),
        summary=f"{lagna.sign} ascendant, {moon.sign} moon, {moon.nakshatra} pada {moon.pada}",
        birth_details=birth_details_out(birth),
        calculation=CalculationOut(
            ayanamsa_degrees=round(ayanamsa, 6),
            year_length_days=YEAR_DAYS,
            julian_day=round(julian_day, 6),
        ),
        lagna=ChartPointOut(**asdict(lagna)),
        moon_sign=ChartPointOut(**asdict(locate_longitude(raw_planets["Moon"][0]))),
        sun_sign=ChartPointOut(**asdict(locate_longitude(sun_longitude))),
        janma_nakshatra=JanmaNakshatraOut(
            name=moon.nakshatra,
            pada=moon.pada,
            lord=moon.nakshatra_lord,
            deity=moon.nakshatra_deity,
        ),
        planets=planets,
        houses=houses,
        yogas=_yogas(planets),
        manglik=_manglik(by_name["Mars"], moon, by_name["Venus"]),
        vimshottari=vimshottari,
    )


def _dignity(name: str, sign: str) -> str:
    if EXALTATION.get(name) == sign:
        return "exalted"
    if sign in OWN_SIGNS.get(name, set()):
        return "own"
    if DEBILITATION.get(name) == sign:
        return "debilitated"
    return "neutral"


def _is_combust(name: str, longitude: float, sun_longitude: float, retrograde: bool) -> bool:
    if name in {"Sun", "Rahu", "Ketu"}:
        return False
    orb = COMBUST_ORB[name]
    if name == "Mercury" and retrograde:
        orb = 12.0
    return _angular_distance(longitude, sun_longitude) <= orb


def _angular_distance(first: float, second: float) -> float:
    difference = abs(first - second) % 360
    return min(difference, 360 - difference)


def _house_number(body_sign_number: int, reference_sign_number: int) -> int:
    return (body_sign_number - reference_sign_number) % 12 + 1


def _yogas(planets: list[PlanetOut]) -> list[YogaOut]:
    by_name = {planet.name: planet for planet in planets}
    found: list[YogaOut] = []
    jupiter = by_name["Jupiter"]
    moon = by_name["Moon"]
    if _house_number(jupiter.sign_number, moon.sign_number) in KENDRA and jupiter.dignity != "debilitated":
        found.append(YogaOut(name="Gaja Kesari", description="Jupiter is in a kendra from the Moon."))
    if by_name["Sun"].sign == by_name["Mercury"].sign:
        found.append(YogaOut(name="Budha-Aditya", description="Sun and Mercury occupy the same sign."))
    if moon.sign == by_name["Mars"].sign:
        found.append(YogaOut(name="Chandra-Mangal", description="Moon and Mars occupy the same sign."))
    mahapurusha = (
        ("Mars", "Ruchaka", "Mars is in its own or exaltation sign and in a kendra from the ascendant."),
        ("Mercury", "Bhadra", "Mercury is in its own or exaltation sign and in a kendra from the ascendant."),
        ("Jupiter", "Hamsa", "Jupiter is in its own or exaltation sign and in a kendra from the ascendant."),
        ("Venus", "Malavya", "Venus is in its own or exaltation sign and in a kendra from the ascendant."),
        ("Saturn", "Sasa", "Saturn is in its own or exaltation sign and in a kendra from the ascendant."),
    )
    for planet_name, yoga_name, description in mahapurusha:
        planet = by_name[planet_name]
        if planet.house in KENDRA and planet.dignity in {"own", "exalted"}:
            found.append(YogaOut(name=yoga_name, description=description))
    return found


def _manglik(mars: PlanetOut, moon: PlanetOut, venus: PlanetOut) -> ManglikOut:
    from_lagna = mars.house in MANGLIK_HOUSES
    from_moon = _house_number(mars.sign_number, moon.sign_number) in MANGLIK_HOUSES
    from_venus = _house_number(mars.sign_number, venus.sign_number) in MANGLIK_HOUSES
    cancelled = from_lagna and mars.dignity in {"own", "exalted"}
    if not from_lagna:
        note = "Mars is not in a manglik house from the ascendant."
    elif cancelled:
        note = "Mars is in a manglik house, in its own or exaltation sign, which is treated as a cancellation."
    else:
        note = "Mars is in a manglik house from the ascendant."
    return ManglikOut(
        manglik_from_lagna=from_lagna,
        manglik_from_moon=from_moon,
        manglik_from_venus=from_venus,
        mars_house_from_lagna=mars.house,
        mars_house_from_moon=_house_number(mars.sign_number, moon.sign_number),
        mars_house_from_venus=_house_number(mars.sign_number, venus.sign_number),
        cancelled=cancelled,
        effective=from_lagna and not cancelled,
        note=note,
    )


def _vimshottari(birth_utc: datetime, moon_longitude: float) -> VimshottariOut:
    longitude = moon_longitude % 360
    nakshatra_index = min(int(longitude / NAKSHATRA_SPAN), 26)
    position = max(0.0, longitude - nakshatra_index * NAKSHATRA_SPAN)
    if position >= NAKSHATRA_SPAN:
        position = NAKSHATRA_SPAN - 1e-9
    lord = DASHA_SEQUENCE[nakshatra_index % 9]
    full_years = DASHA_YEARS[lord]
    elapsed_years = (position / NAKSHATRA_SPAN) * full_years
    balance_years = full_years - elapsed_years
    cycle_start = birth_utc - timedelta(days=elapsed_years * YEAR_DAYS)
    if cycle_start > birth_utc:
        cycle_start = birth_utc

    mahadashas: list[MahadashaOut] = []
    cursor = cycle_start
    for offset in range(9):
        period_lord = DASHA_SEQUENCE[(DASHA_SEQUENCE.index(lord) + offset) % 9]
        period_years = DASHA_YEARS[period_lord]
        period_end = _add_years(cursor, period_years)
        antardashas = _child_periods(cursor, period_end, period_years, period_lord)
        mahadashas.append(
            MahadashaOut(
                lord=period_lord,
                lord_sanskrit=SANSKRIT[period_lord],
                start=cursor,
                end=period_end,
                antardashas=antardashas,
            )
        )
        cursor = period_end

    now = datetime.now(timezone.utc)
    at_birth = _locate(mahadashas, birth_utc)
    if at_birth is None:
        raise ChartCalculationError("Could not place the birth dasha")
    years, months, days, total_days = _split_duration(balance_years)
    return VimshottariOut(
        birth_mahadasha_lord=lord,
        birth_mahadasha_lord_sanskrit=SANSKRIT[lord],
        balance_at_birth=DashaBalanceOut(years=years, months=months, days=days, total_days=total_days),
        at_birth=at_birth,
        current=_locate(mahadashas, now),
        mahadashas=mahadashas,
    )


def _child_periods(start: datetime, end: datetime, duration_years: float, first_lord: str) -> list[DashaSliceOut]:
    first_index = DASHA_SEQUENCE.index(first_lord)
    cursor = start
    periods: list[DashaSliceOut] = []
    for offset in range(9):
        lord = DASHA_SEQUENCE[(first_index + offset) % 9]
        if offset == 8:
            period_end = end
        else:
            period_end = _add_years(cursor, duration_years * DASHA_YEARS[lord] / 120)
            if period_end > end:
                period_end = end
        periods.append(
            DashaSliceOut(lord=lord, lord_sanskrit=SANSKRIT[lord], start=cursor, end=period_end)
        )
        cursor = period_end
    return periods


def _locate(mahadashas: list[MahadashaOut], moment: datetime) -> CurrentDashaOut | None:
    for mahadasha in mahadashas:
        if not (mahadasha.start <= moment < mahadasha.end):
            continue
        antardasha = _period_containing(mahadasha.antardashas, moment)
        if antardasha is None:
            return None
        duration_years = (antardasha.end - antardasha.start).total_seconds() / 86400 / YEAR_DAYS
        pratyantardashas = _child_periods(antardasha.start, antardasha.end, duration_years, antardasha.lord)
        pratyantardasha = _period_containing(pratyantardashas, moment) or pratyantardashas[-1]
        return CurrentDashaOut(
            mahadasha=_slice(mahadasha),
            antardasha=antardasha,
            pratyantardasha=pratyantardasha,
        )
    return None


def _period_containing(periods: list[DashaSliceOut], moment: datetime) -> DashaSliceOut | None:
    for period in periods:
        if period.start <= moment < period.end:
            return period
    if periods and moment == periods[-1].end:
        return periods[-1]
    return None


def _slice(period: MahadashaOut) -> DashaSliceOut:
    return DashaSliceOut(
        lord=period.lord,
        lord_sanskrit=period.lord_sanskrit,
        start=period.start,
        end=period.end,
    )


def _add_years(moment: datetime, years: float) -> datetime:
    return moment + timedelta(days=years * YEAR_DAYS)


def _split_duration(years_float: float) -> tuple[int, int, int, float]:
    total_days = max(years_float, 0) * YEAR_DAYS
    years = int(total_days // YEAR_DAYS)
    remainder = total_days - years * YEAR_DAYS
    month_days = YEAR_DAYS / 12
    months = int(remainder // month_days)
    days = int(round(remainder - months * month_days))
    if days >= int(month_days):
        days = 0
        months += 1
    if months >= 12:
        months = 0
        years += 1
    return years, months, days, round(total_days, 2)
