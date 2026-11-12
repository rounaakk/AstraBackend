"""Birth-place search."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.place import PlaceOut
from app.services.geocode import search_places

router = APIRouter()


@router.get("/search", response_model=list[PlaceOut])
def search(
    q: Annotated[str, Query(min_length=2, max_length=80)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[PlaceOut]:
    return [PlaceOut.model_validate(asdict(place)) for place in search_places(q, limit)]
