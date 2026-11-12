"""Kundali response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.user import BirthDetailsOut


class ChartPointOut(BaseModel):
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


class PlanetOut(ChartPointOut):
    name: str
    sanskrit: str
    house: int
    retrograde: bool
    combust: bool
    dignity: Literal["exalted", "own", "debilitated", "neutral"]


class HouseOut(BaseModel):
    number: int
    sign: str
    sign_sanskrit: str
    sign_number: int
    sign_lord: str
    theme: str
    planets: list[str]


class JanmaNakshatraOut(BaseModel):
    name: str
    pada: int
    lord: str
    deity: str


class YogaOut(BaseModel):
    name: str
    description: str


class ManglikOut(BaseModel):
    manglik_from_lagna: bool
    manglik_from_moon: bool
    manglik_from_venus: bool
    mars_house_from_lagna: int
    mars_house_from_moon: int
    mars_house_from_venus: int
    cancelled: bool
    effective: bool
    note: str


class CalculationOut(BaseModel):
    zodiac: Literal["sidereal"] = "sidereal"
    ayanamsa: Literal["lahiri"] = "lahiri"
    ayanamsa_degrees: float
    house_system: Literal["whole_sign"] = "whole_sign"
    node_type: Literal["mean"] = "mean"
    dasha_system: Literal["vimshottari"] = "vimshottari"
    year_length_days: float
    julian_day: float


class DashaSliceOut(BaseModel):
    lord: str
    lord_sanskrit: str
    start: datetime
    end: datetime


class MahadashaOut(BaseModel):
    lord: str
    lord_sanskrit: str
    start: datetime
    end: datetime
    antardashas: list[DashaSliceOut]


class CurrentDashaOut(BaseModel):
    mahadasha: DashaSliceOut
    antardasha: DashaSliceOut
    pratyantardasha: DashaSliceOut


class DashaBalanceOut(BaseModel):
    years: int
    months: int
    days: int
    total_days: float


class VimshottariOut(BaseModel):
    birth_mahadasha_lord: str
    birth_mahadasha_lord_sanskrit: str
    balance_at_birth: DashaBalanceOut
    at_birth: CurrentDashaOut
    current: CurrentDashaOut | None
    mahadashas: list[MahadashaOut]


class KundaliOut(BaseModel):
    id: str
    user_id: str
    generated_at: datetime
    summary: str
    birth_details: BirthDetailsOut
    calculation: CalculationOut
    lagna: ChartPointOut
    moon_sign: ChartPointOut
    sun_sign: ChartPointOut
    janma_nakshatra: JanmaNakshatraOut
    planets: list[PlanetOut]
    houses: list[HouseOut]
    yogas: list[YogaOut]
    manglik: ManglikOut
    vimshottari: VimshottariOut = Field(description="Vimshottari dasha counted from the Moon")
