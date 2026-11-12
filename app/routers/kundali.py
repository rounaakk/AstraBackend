"""Stored kundali routes."""

from fastapi import APIRouter

from app.deps import CurrentUser
from app.errors import BirthDetailsRequiredError, KundaliNotFoundError
from app.presenters import stored_kundali
from app.schemas.kundali import KundaliOut
from app.services.kundali import generate_kundali
from app.store.memory import store

router = APIRouter()


@router.get("/me", response_model=KundaliOut)
def get_my_kundali(user: CurrentUser) -> KundaliOut:
    chart = stored_kundali(user.id)
    if chart is None:
        raise KundaliNotFoundError("No kundali is stored yet. Add birth details first.")
    return chart


@router.post("/generate", response_model=KundaliOut)
def generate_my_kundali(user: CurrentUser) -> KundaliOut:
    if user.birth is None:
        raise BirthDetailsRequiredError("Add date, time, and place of birth first")
    chart = generate_kundali(user.id, user.birth)
    store.save_kundali(user.id, chart.model_dump(mode="json"))
    return chart
