# Astra API

Python backend for the Astra astrology app. It stores accounts and kundali charts in memory and exposes a JSON API for a React Native client.

Accounts, refresh sessions, and charts live in the API process. Restarting the server clears them. Run one worker so every request shares the same store.

## Run

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Set `SECRET_KEY` before deploying. Optional: `ACCESS_TOKEN_MINUTES` (default 1440) and `REFRESH_TOKEN_DAYS` (default 30).

```bash
pytest
```

## Auth

Send `Authorization: Bearer <access_token>` and `Content-Type: application/json`.

A 10-digit Indian mobile number is stored as `+91...`. Login accepts an email or a phone number in `identifier`.

Logout revokes the refresh token. Changing the password revokes existing access tokens and returns a new pair.

```javascript
const response = await fetch(`${API_URL}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    identifier: "asha@example.com",
    password: "starlight-7",
  }),
});
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Create an account. Birth details are optional and, when sent, a kundali is stored immediately. |
| `POST` | `/api/v1/auth/login` | Log in with email or phone. Returns the stored kundali when one exists. |
| `POST` | `/api/v1/auth/refresh` | Exchange a refresh token for a new pair. The previous refresh token stops working. |
| `POST` | `/api/v1/auth/logout` | Revoke a refresh token. |
| `POST` | `/api/v1/auth/change-password` | Change the password and receive new tokens. |
| `GET` | `/api/v1/users/me` | Current profile, birth details, and `has_kundali`. |
| `PATCH` | `/api/v1/users/me` | Update name, email, phone, or gender. |
| `GET` | `/api/v1/users/me/birth-details` | Stored date, time, and place of birth. |
| `PUT` | `/api/v1/users/me/birth-details` | Save birth details and store a new kundali. |
| `GET` | `/api/v1/kundali/me` | Stored kundali for the logged-in user. |
| `POST` | `/api/v1/kundali/generate` | Recompute the kundali from the saved birth details. |
| `GET` | `/api/v1/places/search?q=pune` | Match a birth place against the bundled city list. |

`PUT /api/v1/users/me/birth-details` accepts:

```json
{
  "date_of_birth": "1994-11-02",
  "time_of_birth": "06:45:00",
  "place_of_birth": "Pune"
}
```

`latitude`, `longitude`, and `timezone` are optional. Pass all three when the place is not in the city list. Unknown names fall back to OpenStreetMap Nominatim unless `ASTRA_DISABLE_REMOTE_GEOCODE=1`.

## Kundali

Charts use the Lahiri sidereal zodiac, whole-sign houses counted from the ascendant, mean Rahu, and Vimshottari dasha from the Moon. House 1 is the ascendant sign. Each planet includes its sign, nakshatra, pada, navamsa, house, dignity, retrograde flag, and combustion flag.

The response also includes the birth nakshatra, a manglik check from the ascendant, Moon, and Venus, a few standard yogas, and mahadasha / antardasha periods. The current period includes the pratyantardasha.
