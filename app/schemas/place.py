"""Place search results."""

from pydantic import BaseModel


class PlaceOut(BaseModel):
    name: str
    region: str
    country: str
    label: str
    latitude: float
    longitude: float
    timezone: str
