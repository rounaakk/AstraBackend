"""Registration, login, and session routes."""

from fastapi import APIRouter, Response, status

from app.deps import CurrentUser
from app.presenters import auth_response
from app.schemas.auth import AuthResponse, ChangePasswordIn, LoginIn, LogoutIn, RefreshIn, RegisterIn
from app.services import auth as auth_service
from app.services.birth import build_birth_details
from app.services.kundali import generate_kundali
from app.store.memory import store

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn) -> AuthResponse:
    birth = build_birth_details(payload.birth_details) if payload.birth_details else None
    user = auth_service.create_account(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        gender=payload.gender,
    )
    try:
        if birth is not None:
            chart = generate_kundali(user.id, birth)
            store.save_birth_and_kundali(user.id, birth, chart.model_dump(mode="json"))
    except Exception:
        store.delete_user(user.id)
        raise
    return auth_response(user, auth_service.issue_tokens(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginIn) -> AuthResponse:
    user = auth_service.authenticate(payload.identifier, payload.password)
    return auth_response(user, auth_service.issue_tokens(user))


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshIn) -> AuthResponse:
    user = auth_service.rotate_refresh(payload.refresh_token)
    return auth_response(user, auth_service.issue_tokens(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutIn) -> Response:
    auth_service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", response_model=AuthResponse)
def change_password(payload: ChangePasswordIn, user: CurrentUser) -> AuthResponse:
    updated = auth_service.change_password(user, payload.current_password, payload.new_password)
    return auth_response(updated, auth_service.issue_tokens(updated))
