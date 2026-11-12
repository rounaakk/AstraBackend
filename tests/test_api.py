"""HTTP coverage for accounts, birth details, and stored kundalis."""

from datetime import date, timedelta


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, email="asha@example.com", phone="9876543210", birth=True):
    payload = {
        "full_name": "Asha Rao",
        "email": email,
        "phone": phone,
        "password": "starlight-7",
        "gender": "female",
    }
    if birth:
        payload["birth_details"] = {
            "date_of_birth": "1994-11-02",
            "time_of_birth": "06:45:00",
            "place_of_birth": "Pune",
        }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["store"] == "memory"


def test_register_login_and_stored_kundali(client):
    created = _register(client)
    assert created["user"]["phone"] == "+919876543210"
    assert created["user"]["has_kundali"] is True
    chart = created["kundali"]
    assert chart["summary"]
    assert len(chart["planets"]) == 9
    assert len(chart["houses"]) == 12
    assert chart["houses"][0]["sign"] == chart["lagna"]["sign"]
    assert chart["birth_details"]["label"] == "Pune, Maharashtra, India"
    assert chart["calculation"]["ayanamsa"] == "lahiri"
    assert chart["calculation"]["house_system"] == "whole_sign"

    me = client.get("/api/v1/users/me", headers=_headers(created["access_token"]))
    assert me.status_code == 200
    assert me.json()["birth_details"]["timezone"] == "Asia/Kolkata"

    stored = client.get("/api/v1/kundali/me", headers=_headers(created["access_token"]))
    assert stored.status_code == 200
    assert stored.json()["id"] == chart["id"]

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"identifier": "9876543210", "password": "starlight-7"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["kundali"]["id"] == chart["id"]


def test_duplicate_email_and_bad_password(client):
    _register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Someone Else",
            "email": "asha@example.com",
            "phone": "9876543211",
            "password": "starlight-7",
        },
    )
    assert duplicate.status_code == 409

    short_password = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Someone Else",
            "email": "other@example.com",
            "phone": "9876543211",
            "password": "short",
        },
    )
    assert short_password.status_code == 422

    invalid = client.post(
        "/api/v1/auth/login",
        json={"identifier": "asha@example.com", "password": "wrong-password"},
    )
    assert invalid.status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401


def test_refresh_logout_and_password_change(client):
    created = _register(client, birth=False)
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert rotated.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]}).status_code == 401

    logged_out = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": rotated.json()["refresh_token"]},
    )
    assert logged_out.status_code == 204

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=_headers(created["access_token"]),
        json={"current_password": "starlight-7", "new_password": "starlight-8"},
    )
    assert changed.status_code == 200
    assert client.get("/api/v1/users/me", headers=_headers(created["access_token"])).status_code == 401
    assert client.get("/api/v1/users/me", headers=_headers(changed.json()["access_token"])).status_code == 200


def test_birth_details_update_is_private(client):
    first = _register(client, email="one@example.com", phone="9000000001", birth=False)
    second = _register(client, email="two@example.com", phone="9000000002", birth=False)
    first_headers = _headers(first["access_token"])
    second_headers = _headers(second["access_token"])

    missing = client.get("/api/v1/kundali/me", headers=first_headers)
    assert missing.status_code == 404

    saved = client.put(
        "/api/v1/users/me/birth-details",
        headers=first_headers,
        json={
            "date_of_birth": "1990-08-15",
            "time_of_birth": "10:30:00",
            "place_of_birth": "Home",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
        },
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["planets"]) == 9

    profile = client.patch("/api/v1/users/me", headers=first_headers, json={"full_name": "Asha R"})
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Asha R"
    assert profile.json()["has_kundali"] is True

    other = client.get("/api/v1/kundali/me", headers=second_headers)
    assert other.status_code == 404
    mine = client.get("/api/v1/kundali/me", headers=first_headers)
    assert mine.json()["user_id"] == first["user"]["id"]
    assert mine.json()["user_id"] != second["user"]["id"]


def test_unknown_and_future_birth_place(client):
    created = _register(client, birth=False)
    headers = _headers(created["access_token"])
    unknown = client.put(
        "/api/v1/users/me/birth-details",
        headers=headers,
        json={
            "date_of_birth": "1990-08-15",
            "time_of_birth": "10:30:00",
            "place_of_birth": "TotallyUnknownVilleXYZ",
        },
    )
    assert unknown.status_code == 422

    future = client.put(
        "/api/v1/users/me/birth-details",
        headers=headers,
        json={
            "date_of_birth": (date.today() + timedelta(days=2)).isoformat(),
            "time_of_birth": "10:30:00",
            "place_of_birth": "Pune",
        },
    )
    assert future.status_code == 422


def test_place_search_accepts_aliases(client):
    response = client.get("/api/v1/places/search", params={"q": "bangalore"})
    assert response.status_code == 200
    labels = [place["label"] for place in response.json()]
    assert "Bengaluru, Karnataka, India" in labels
