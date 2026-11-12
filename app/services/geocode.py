"""Resolve a birth place to coordinates and an IANA timezone."""

import logging
import os
import re
import threading
from dataclasses import dataclass

import httpx

from app.data.cities import CITIES, City
from app.errors import AmbiguousPlaceError, PlaceNotFoundError

logger = logging.getLogger(__name__)

_cache: dict[str, "ResolvedPlace"] = {}
_cache_lock = threading.Lock()
_finder = None
_finder_lock = threading.Lock()


@dataclass(frozen=True)
class ResolvedPlace:
    name: str
    region: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    label: str


def search_places(query: str, limit: int = 8) -> list[ResolvedPlace]:
    return [_from_city(city) for city, score in _ranked(query) if score >= 70][:limit]


def resolve_place(
    place_name: str,
    latitude: float | None,
    longitude: float | None,
    timezone_name: str | None,
) -> ResolvedPlace:
    place_name = " ".join(place_name.split())
    if latitude is not None and longitude is not None:
        timezone_name = timezone_name or _timezone_for(latitude, longitude)
        _validate_timezone(timezone_name)
        resolved_name = place_name
        region = ""
        country = ""
        best = _best(place_name)
        if best is not None and best[1] == 100:
            resolved_name = best[0].name
            region = best[0].region
            country = best[0].country
        label = ", ".join(part for part in (resolved_name, region, country) if part)
        return ResolvedPlace(resolved_name, region, country, latitude, longitude, timezone_name, label)

    strong = [(city, score) for city, score in _ranked(place_name) if score >= 90]
    if strong:
        if len(strong) > 1 and strong[0][1] - strong[1][1] < 10:
            raise AmbiguousPlaceError(
                f"Multiple places match '{place_name}'. Choose one or pass latitude and longitude.",
                [_candidate(city) for city, _score in strong[:5]],
            )
        return _from_city(strong[0][0])

    remote = _nominatim(place_name)
    if remote is None:
        raise PlaceNotFoundError(
            f"No matching place for '{place_name}'. Try a nearby city, or pass latitude, longitude, and timezone."
        )
    return remote


def _ranked(query: str) -> list[tuple[City, int]]:
    scored = [(city, _score(query, city)) for city in CITIES]
    scored = [item for item in scored if item[1] > 0]
    scored.sort(key=lambda item: (-item[1], item[0].name))
    return scored


def _best(query: str) -> tuple[City, int] | None:
    ranked = _ranked(query)
    return ranked[0] if ranked else None


def _score(query: str, city: City) -> int:
    normalized_query = _normalize(query)
    if not normalized_query:
        return 0
    labels = (city.name, *city.aliases)
    for label in labels:
        normalized_label = _normalize(label)
        qualified = {
            normalized_label,
            _normalize(f"{label} {city.region}"),
            _normalize(f"{label} {city.country}"),
            _normalize(f"{label} {city.region} {city.country}"),
        }
        if normalized_query in qualified:
            return 100
    best = 0
    padded_query = f" {normalized_query} "
    for label in labels:
        normalized_label = _normalize(label)
        if (
            f" {normalized_label} " in padded_query
            or normalized_query.startswith(normalized_label + " ")
            or normalized_query.endswith(" " + normalized_label)
        ):
            best = max(best, 90)
        elif len(normalized_query) >= 3 and normalized_label.startswith(normalized_query):
            best = max(best, 80)
        elif len(normalized_query) >= 4 and normalized_query in normalized_label:
            best = max(best, 70)
    return best


def _normalize(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def _from_city(city: City) -> ResolvedPlace:
    label = ", ".join(part for part in (city.name, city.region, city.country) if part)
    return ResolvedPlace(
        name=city.name,
        region=city.region,
        country=city.country,
        latitude=city.latitude,
        longitude=city.longitude,
        timezone=city.timezone,
        label=label,
    )


def _candidate(city: City) -> dict:
    place = _from_city(city)
    return {
        "label": place.label,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "timezone": place.timezone,
    }


def _timezone_for(latitude: float, longitude: float) -> str:
    timezone_name = _timezone_finder().timezone_at(lat=latitude, lng=longitude)
    if timezone_name:
        return timezone_name
    if 6.5 <= latitude <= 37.5 and 68.0 <= longitude <= 97.5:
        return "Asia/Kolkata"
    raise PlaceNotFoundError(
        "Could not determine a timezone for these coordinates. Pass a timezone such as Asia/Kolkata."
    )


def _timezone_finder():
    global _finder
    if _finder is None:
        with _finder_lock:
            if _finder is None:
                from timezonefinder import TimezoneFinder

                _finder = TimezoneFinder()
    return _finder


def _validate_timezone(timezone_name: str) -> None:
    from zoneinfo import ZoneInfo

    try:
        ZoneInfo(timezone_name)
    except Exception as exc:
        raise PlaceNotFoundError(f"Unknown timezone '{timezone_name}'") from exc


def _nominatim(query: str) -> ResolvedPlace | None:
    if os.getenv("ASTRA_DISABLE_REMOTE_GEOCODE") == "1":
        return None
    key = _normalize(query)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": "AstraBackend/1.0 (astrology birth place lookup)"},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        logger.warning("Place lookup failed for %s", query)
        return None
    if not payload:
        return None
    hit = payload[0]
    latitude = float(hit["lat"])
    longitude = float(hit["lon"])
    timezone_name = _timezone_for(latitude, longitude)
    resolved = ResolvedPlace(
        name=query,
        region="",
        country="",
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
        label=hit.get("display_name") or query,
    )
    with _cache_lock:
        _cache[key] = resolved
    return resolved
