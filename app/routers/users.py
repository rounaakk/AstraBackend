"""Profile and birth-detail routes."""

from fastapi import APIRouter

from app.deps import CurrentUser
from app.errors import BirthDetailsRequiredError
from app.presenters import birth_details_out, user_out
from app.schemas.kundali import KundaliOut
from app.schemas.user import BirthDetailsIn, BirthDetailsOut, UpdateProfileIn, UserOut
from app.services import auth as auth_service
from app.services.birth import build_birth_details
from app.services.kundali import generate_kundali
from app.store.memory import store

router = APIRouter()


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: UpdateProfileIn, user: CurrentUser) -> UserOut:
    updated = auth_service.apply_profile_changes(user.id, payload.model_dump(exclude_unset=True))
    return user_out(updated)


@router.get("/me/birth-details", response_model=BirthDetailsOut)
def get_birth_details(user: CurrentUser) -> BirthDetailsOut:
    if user.birth is None:
        raise BirthDetailsRequiredError("Add date, time, and place of birth first")
    return birth_details_out(user.birth)


@router.put("/me/birth-details", response_model=KundaliOut)
def save_birth_details(payload: BirthDetailsIn, user: CurrentUser) -> KundaliOut:
    birth = build_birth_details(payload)
    chart = generate_kundali(user.id, birth)
    store.save_birth_and_kundali(user.id, birth, chart.model_dump(mode="json"))
    return chart
