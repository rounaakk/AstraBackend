# Astra Backend Contract — `https://astratga.com/apis/v1`

Version: **v1 (draft 1)** · Consumers: Astra mobile/web app (`src/api/*`)
Everything the app calls is listed here. The backend must implement the **Required** endpoints; **Optional** endpoints are referenced by the design but can land later (the client feature-detects via `GET /config`).

---

## 0. Conventions

| Topic | Rule |
|---|---|
| Base URL | `https://astratga.com/apis/v1` (overridable per environment via `EXPO_PUBLIC_API_BASE_URL`) |
| Transport | HTTPS only, JSON request/response bodies, UTF-8 |
| Auth | `Authorization: Bearer <accessToken>` on every endpoint marked 🔒 |
| IDs | Opaque strings (UUID v7 / ULID recommended) |
| Timestamps | ISO-8601 UTC with `Z`, e.g. `2025-03-04T10:15:30Z` |
| Civil birth data | `birthDate` = `YYYY-MM-DD`, `birthTime` = `HH:mm` (24 h) — **local to the birthplace**, never converted on the client |
| Timezone | IANA name, e.g. `Asia/Kolkata` |
| Empty success | `204 No Content` |
| Versioning | Path-versioned (`/v1`). Additive changes are non-breaking; removals require `/v2`. |
| Rate limits | Respond `429` with `Retry-After` seconds. Auth endpoints: ≤ 10 req/min per IP+email. Places search: ≤ 60 req/min per client. |
| CORS (web) | Allow app origins; allow headers listed below; expose `X-Request-Id`, `Retry-After`. |

### Request headers sent by the client

| Header | Example | Notes |
|---|---|---|
| `Content-Type` | `application/json` | on bodies |
| `Accept` | `application/json` | |
| `Authorization` | `Bearer eyJ…` | 🔒 endpoints |
| `X-Request-Id` | `0191c2e0-…` | UUID per request; echo back in responses and logs |
| `X-Client-Platform` | `ios` / `android` / `web` | |
| `X-Client-Version` | `1.0.0+12` | app version + build |
| `Accept-Language` | `en-IN` | for messages and place names |
| `Idempotency-Key` | UUID | on `POST /auth/signup/email`, `POST /auth/social`; backend must return the original response for a replay within 24 h |

### Error envelope (all non-2xx)

```json
{
  "error": {
    "code": "EMAIL_TAKEN",
    "message": "An account with this email already exists.",
    "details": { "providers": ["email"] },
    "requestId": "0191c2e0-…"
  }
}
```

`message` is developer-facing English; the client maps `code` to its own copy. `details` is optional and code-specific. Validation errors use:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "…",
  "details": { "fields": { "email": "INVALID_FORMAT", "password": "TOO_SHORT" } } } }
```

### Error codes

| HTTP | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Body/query fails validation (`details.fields`) |
| 400 | `BAD_REQUEST` | Malformed JSON etc. |
| 401 | `UNAUTHENTICATED` | Missing/invalid access token |
| 401 | `TOKEN_EXPIRED` | Access token expired → client refreshes and retries once |
| 401 | `INVALID_REFRESH_TOKEN` | Refresh token unknown, expired, revoked, or **reused** (family revoked) |
| 401 | `INVALID_CREDENTIALS` | Wrong email/password (never reveal which) |
| 401 | `PROVIDER_TOKEN_INVALID` | Social token failed verification (signature, aud, exp, nonce) |
| 403 | `FORBIDDEN` | Authenticated but not allowed |
| 403 | `EMAIL_NOT_VERIFIED` | Only if an endpoint is gated on verification (none in v1) |
| 404 | `NOT_FOUND` | Resource missing |
| 409 | `EMAIL_TAKEN` | Sign-up email already has a password identity |
| 409 | `PROVIDER_MISMATCH` | Email exists on another provider; `details.providers` lists them |
| 409 | `IDENTITY_ALREADY_LINKED` | Provider account belongs to a different user |
| 422 | `PROVIDER_EMAIL_MISSING` | Provider returned no email and none was supplied |
| 422 | `PLACE_NOT_FOUND` | `placeId` unknown |
| 429 | `RATE_LIMITED` | Too many requests (`Retry-After`) |
| 500 | `INTERNAL` | Unhandled |
| 503 | `SERVICE_UNAVAILABLE` | Maintenance / dependency down |

---

## 1. Shared schemas

### `User`
```json
{
  "id": "usr_01J…",
  "email": "ana@example.com",
  "emailVerified": false,
  "name": "Ana",
  "providers": ["email", "google"],
  "createdAt": "2025-03-04T10:15:30Z",
  "updatedAt": "2025-03-04T10:15:30Z"
}
```
`email` may be `null` (Facebook without email permission). `providers` ⊆ `email | google | facebook | apple`.

### `BirthPlace`
```json
{
  "placeId": "plc_…",
  "name": "Pune",
  "region": "Maharashtra",
  "countryCode": "IN",
  "lat": 18.5204,
  "lon": 73.8567,
  "timezone": "Asia/Kolkata"
}
```

### `Profile`
```json
{
  "name": "Ana",
  "birthDate": "1994-11-02",
  "birthTime": "06:40",
  "birthTimeKnown": true,
  "birthPlace": { "…BirthPlace" },
  "birthInstantUtc": "1994-11-02T01:10:00Z",
  "sunSign": "scorpio",
  "moonSign": "gemini",
  "risingSign": "libra",
  "sunSignOverride": null,
  "updatedAt": "2025-03-04T10:15:30Z"
}
```
- `birthInstantUtc`, `sunSign`, `moonSign`, `risingSign` are **derived by the backend** (read-only).
- `sunSign` needs `birthDate`; `moonSign` needs date (+ place for edge cases); `risingSign` needs `birthTimeKnown=true` + `birthPlace`. Otherwise `null`.
- Sign ids: `aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces`.

### `ProfileInput` (client → server)
```json
{
  "name": "Ana",
  "birthDate": "1994-11-02",
  "birthTime": "06:40",
  "birthTimeKnown": true,
  "birthPlace": { "placeId": "plc_…" },
  "sunSignOverride": null
}
```
Validation: `name` 2–80 chars; `birthDate` between `1900-01-01` and today; `birthTime` required iff `birthTimeKnown`; `birthPlace` either `{ placeId }` **or** a manual `{ name, countryCode, lat, lon, timezone }` (for the offline/manual fallback); all fields optional on `PATCH`-style use but `PUT /me/profile` replaces the whole object.

### `Session`
```json
{
  "sessionId": "ses_…",
  "tokenType": "Bearer",
  "accessToken": "eyJ…",
  "accessTokenExpiresAt": "2025-03-04T10:30:30Z",
  "refreshToken": "rt_…",
  "refreshTokenExpiresAt": "2025-05-03T10:15:30Z"
}
```
- Access token: JWT (RS256/ES256), **15 min**, claims `sub` (user id), `sid` (session id), `iat`, `exp`, `iss=astratga.com`, `aud=astra-app`.
- Refresh token: opaque, **60 days**, single-use, **rotated** on every `/auth/refresh`; reuse of a consumed token revokes the whole session family.

### `DeviceInfo` (client → server, optional on auth calls)
```json
{ "platform": "ios", "osVersion": "18.3", "appVersion": "1.0.0+12", "model": "iPhone15,3", "installId": "inst_…" }
```
`installId` is a random UUID generated once per install (used to name sessions and for funnel analytics).

### `AuthResult`
```json
{ "user": { "…User" }, "profile": { "…Profile" }, "session": { "…Session" }, "isNewUser": true }
```

---

## 2. Auth — Required

### `POST /auth/signup/email`
Create an account with email + password. Accepts the onboarding draft so the profile is created atomically.

Headers: `Idempotency-Key`
```json
{
  "email": "ana@example.com",
  "password": "correct horse battery",
  "name": "Ana",
  "profile": { "…ProfileInput without name" },
  "device": { "…DeviceInfo" },
  "acceptedTermsVersion": "2025-01"
}
```
Rules: email normalised (trim, lowercase); password ≥ 8 chars (≤ 128), hashed with Argon2id; `profile` optional.
Responses: `201 AuthResult` (`isNewUser: true`) · `409 EMAIL_TAKEN` · `409 PROVIDER_MISMATCH { providers }` · `400 VALIDATION_ERROR` · `429`.
Side effect: queue a verification email (non-blocking).

### `POST /auth/login/email`
```json
{ "email": "ana@example.com", "password": "…", "device": { "…DeviceInfo" } }
```
Responses: `200 AuthResult` (`isNewUser: false`) · `401 INVALID_CREDENTIALS` · `409 PROVIDER_MISMATCH` (email exists with social only, no password) · `429`.

### `POST /auth/social`
Sign up **or** log in with a provider credential. The backend verifies the token, finds the identity, links or creates the user, and returns a session.

Headers: `Idempotency-Key`
```json
{
  "provider": "google",
  "credential": {
    "idToken": "eyJ…"
  },
  "name": "Ana",
  "profile": { "…ProfileInput without name" },
  "device": { "…DeviceInfo" },
  "acceptedTermsVersion": "2025-01"
}
```
`credential` shape per provider:

| provider | credential | Verification the backend must perform |
|---|---|---|
| `google` | `{ "idToken": string, "nonce"?: string }` | Validate JWT against Google JWKS (`https://www.googleapis.com/oauth2/v3/certs`); `iss ∈ {accounts.google.com, https://accounts.google.com}`; `aud == GOOGLE_WEB_CLIENT_ID`; `exp`; use `sub` as providerUserId; `email`, `email_verified`, `name`, `picture`. |
| `facebook` (classic) | `{ "accessToken": string }` | `GET graph.facebook.com/debug_token?input_token=…&access_token=APP_ID|APP_SECRET` → `is_valid`, `app_id == FACEBOOK_APP_ID`; then `GET /me?fields=id,name,email` with the user token. |
| `facebook` (iOS Limited Login) | `{ "authenticationToken": string, "nonce": string }` | OIDC JWT: verify against `https://www.facebook.com/.well-known/oauth/openid/jwks/`; `iss == https://www.facebook.com`; `aud == FACEBOOK_APP_ID`; `nonce` matches; `sub`, `email`, `name`. |
| `apple` | `{ "identityToken": string, "authorizationCode": string, "nonce": string, "fullName"?: { "givenName"?: string, "familyName"?: string }, "email"?: string }` | Verify JWT against `https://appleid.apple.com/auth/keys`; `iss == https://appleid.apple.com`; `aud == APPLE_BUNDLE_ID` (iOS) or `APPLE_SERVICES_ID` (web); `nonce` (sha256) matches; persist `fullName`/`email` from the first call (Apple sends them only once). Optionally exchange `authorizationCode` for a refresh token to support revocation checks. |

Name precedence for a **new** user: `body.name` → provider name → `"Stargazer"`.
Email precedence: provider email (verified) → `body.email`? *(not accepted; email must come from the provider)* → `422 PROVIDER_EMAIL_MISSING`.

Linking rules:
1. Identity `(provider, providerUserId)` exists → log in that user.
2. Else provider email is **verified** and matches an existing user → create identity on that user (auto-link), `isNewUser: false`.
3. Else provider email matches a user but is unverified → `409 PROVIDER_MISMATCH { providers }`.
4. Else create user + identity (+ profile if supplied), `isNewUser: true`.

Responses: `200 AuthResult` · `401 PROVIDER_TOKEN_INVALID` · `409 PROVIDER_MISMATCH` · `409 IDENTITY_ALREADY_LINKED` · `422 PROVIDER_EMAIL_MISSING` · `429`.

### `POST /auth/refresh`
```json
{ "refreshToken": "rt_…" }
```
Responses: `200 { "session": Session }` (new pair; old refresh token invalidated) · `401 INVALID_REFRESH_TOKEN`.
Must be safe under concurrent calls from one client within a 10 s grace window (return the same new pair or accept the previous token once) to tolerate races.

### `POST /auth/logout` 🔒
```json
{ "refreshToken": "rt_…", "allDevices": false }
```
Revokes the current session (or all sessions of the user when `allDevices=true`). Always `204`, even if the token was already invalid.

### `POST /auth/password/forgot`
```json
{ "email": "ana@example.com" }
```
Always `202` (do not reveal account existence). Sends an email with deep link `https://astratga.com/reset-password?token=…` (universal link → `astra://reset-password?token=…`). Token valid 30 min, single use.

### `POST /auth/password/reset`
```json
{ "token": "prt_…", "newPassword": "…" }
```
Responses: `204` (and revoke all sessions) · `400 VALIDATION_ERROR` · `401 INVALID_CREDENTIALS` (bad/expired token).

### `POST /auth/email/verify/request` 🔒
No body. `202`. Rate-limited to 1/min per user.

### `POST /auth/email/verify/confirm`
```json
{ "token": "evt_…" }
```
`204` · `401 INVALID_CREDENTIALS`.

---

## 3. Current user — Required

### `GET /me` 🔒
`200 { "user": User, "profile": Profile | null }`
Called on every cold start to reconcile the local cache. Support `If-None-Match`/`ETag` → `304` (optional).

### `PATCH /me` 🔒
```json
{ "name": "Ana M." }
```
Changeable: `name`. (Email change is out of scope for v1.) `200 { "user": User }`.

### `PUT /me/profile` 🔒
Body: `ProfileInput`. Replaces the profile and recomputes derived signs. `200 { "profile": Profile }` · `422 PLACE_NOT_FOUND` · `400`.

### `GET /me/profile` 🔒
`200 { "profile": Profile | null }`.

### `DELETE /me` 🔒
```json
{ "confirmation": "DELETE" }
```
Deletes the user, identities, profile, sessions (hard delete or ≤ 30-day grace per policy). `204`. Required by App Store / Google Play account-deletion policies.

### `GET /me/sessions` 🔒
`200 { "sessions": [ { "sessionId", "platform", "model", "createdAt", "lastSeenAt", "current": true } ] }`

### `DELETE /me/sessions/{sessionId}` 🔒
`204`.

---

## 4. Places — Required (used by Card 2 and Settings)

### `GET /places/search?q=pun&limit=6&lang=en`
Geocoder proxy (e.g. Mapbox/Google Places/Nominatim on the backend — key never ships to clients). Returns populated places only (cities, towns, villages), with timezone resolved.
```json
{ "places": [ { "…BirthPlace" }, … ] }
```
`q` ≥ 2 chars; `limit` 1–10 (default 6). Cache aggressively (results are static). `400` if `q` too short.

### `GET /places/{placeId}` — Optional
`200 { "place": BirthPlace }` · `404`.

---

## 5. Configuration — Required (tiny)

### `GET /config`
Public, cached 5 min by the client.
```json
{
  "minAppVersion": { "ios": "1.0.0", "android": "1.0.0", "web": "1.0.0" },
  "auth": { "google": true, "facebook": true, "apple": true, "email": true, "passwordless": false },
  "features": { "placesSearch": true, "anonymousSessions": false, "events": true },
  "legal": { "termsVersion": "2025-01", "termsUrl": "https://astratga.com/terms", "privacyUrl": "https://astratga.com/privacy" }
}
```
The client hides a provider button if its flag is `false` (in addition to missing local keys).

---

## 6. Optional endpoints (referenced by design options)

### `POST /auth/anonymous` — Option "anonymous session"
```json
{ "device": DeviceInfo, "profile": ProfileInput }
```
`201 AuthResult` with `user.providers = []`, `user.email = null`, `isNewUser: true`. Later `POST /auth/social` / `POST /auth/signup/email` called **with** a Bearer anonymous token upgrades that user in place (keeps `user.id`) instead of creating a new one.

### `POST /auth/passwordless/start` / `POST /auth/passwordless/verify` — Option "email codes"
```json
{ "email": "ana@example.com" }                       → 202 { "challengeId": "chl_…", "expiresInSec": 600 }
{ "challengeId": "chl_…", "code": "482913", "name"?: "…", "profile"?: ProfileInput, "device"?: DeviceInfo } → 200 AuthResult
```
6-digit code, 10 min TTL, 5 attempts.

### `POST /me/identities/link` 🔒 / `DELETE /me/identities/{provider}` 🔒 — account linking from Settings
Body for link: `{ "provider", "credential" }` (same as `/auth/social`). `200 { "user": User }` · `409 IDENTITY_ALREADY_LINKED`. Unlink refuses (`400`) if it would leave the user with no way to log in.

### `POST /me/devices` 🔒 — push tokens (future)
`{ "installId", "platform", "pushToken", "pushProvider": "expo" }` → `204`.

### `POST /events` — funnel analytics (public, batched)
```json
{ "installId": "inst_…", "events": [
  { "name": "onboarding_card_viewed", "ts": "…", "props": { "card": 1 } },
  { "name": "onboarding_completed",   "ts": "…", "props": { "hasBirthTime": true, "hasPlace": false } },
  { "name": "auth_started",           "ts": "…", "props": { "provider": "google", "mode": "signup" } },
  { "name": "auth_succeeded",         "ts": "…", "props": { "provider": "google", "isNewUser": true } },
  { "name": "auth_failed",            "ts": "…", "props": { "provider": "email", "code": "EMAIL_TAKEN" } }
] }
```
`202`. Max 50 events per call.

### `GET /health`
`200 { "status": "ok", "version": "…" }`.

---

## 7. Endpoint index

| Method | Path | Auth | Status | Used by |
|---|---|---|---|---|
| POST | `/auth/signup/email` | – | Required | SignUpScreen |
| POST | `/auth/login/email` | – | Required | LogInScreen |
| POST | `/auth/social` | – | Required | useSocialAuth (both screens) |
| POST | `/auth/refresh` | – | Required | http.ts (automatic) |
| POST | `/auth/logout` | 🔒 | Required | Settings → Log out |
| POST | `/auth/password/forgot` | – | Required | ForgotPasswordScreen |
| POST | `/auth/password/reset` | – | Required | ResetPasswordScreen |
| POST | `/auth/email/verify/request` | 🔒 | Required | Settings banner |
| POST | `/auth/email/verify/confirm` | – | Required | deep link |
| GET | `/me` | 🔒 | Required | SessionProvider boot |
| PATCH | `/me` | 🔒 | Required | Settings (name) |
| GET | `/me/profile` | 🔒 | Required | Settings |
| PUT | `/me/profile` | 🔒 | Required | Settings (birth details) |
| DELETE | `/me` | 🔒 | Required | Settings → Delete account |
| GET | `/me/sessions` | 🔒 | Required | Settings (phase 2 UI) |
| DELETE | `/me/sessions/{id}` | 🔒 | Required | Settings (phase 2 UI) |
| GET | `/places/search` | – | Required | PlaceSearchField |
| GET | `/places/{placeId}` | – | Optional | — |
| GET | `/config` | – | Required | App boot |
| POST | `/auth/anonymous` | – | Optional | (option) |
| POST | `/auth/passwordless/start` · `/verify` | – | Optional | (option) |
| POST | `/me/identities/link` · DELETE `/me/identities/{provider}` | 🔒 | Optional | Settings (phase 2) |
| POST | `/me/devices` | 🔒 | Optional | (future push) |
| POST | `/events` | – | Optional | analytics |
| GET | `/health` | – | Optional | ops |

---

## 8. Backend environment (for reference, never shipped to clients)

```
GOOGLE_WEB_CLIENT_ID=            # must equal the app's EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID (token audience)
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
APPLE_BUNDLE_ID=                 # e.g. com.astratga.astra
APPLE_SERVICES_ID=               # web only
APPLE_TEAM_ID= / APPLE_KEY_ID= / APPLE_PRIVATE_KEY=
JWT_PRIVATE_KEY= / JWT_PUBLIC_KEY=   # ES256
GEOCODER_PROVIDER= / GEOCODER_API_KEY=
EMAIL_PROVIDER_API_KEY=
```
