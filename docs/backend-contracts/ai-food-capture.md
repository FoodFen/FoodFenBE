# AI food capture — API contract

Endpoints: `POST /ai/food/analyze-image`, `POST /ai/food/analyze-text`, `GET /ai/food/quota`.
Wire format is camelCase. Failure bodies are `{message, ...}` (see `docs/authentication.md`).

## Identity

Every AI call identifies its caller one of two ways:

| Caller | Headers |
|---|---|
| Anonymous | `X-Device-Id: <opaque string, 1-64 chars>` (a UUID, generated once and kept in secure storage) |
| Signed in | `Authorization: Bearer <access token>`. `X-Device-Id` is optional but should still be sent. |

Neither header present: **401** (as before). An invalid or expired Bearer: **401**. An empty or over-long
`X-Device-Id`: **422**. Anonymous callers never get any status other than 401, 403 (trials used up),
422, 429 (rate limit), or the normal analysis errors (400 unsupported image, 5xx).

## Free trials

- Successful analyses per input method **per day**: **3 for a guest** (anonymous device), **5 for a signed-in
  free user**. Methods are `image`, `text`, `voice`, three independent counters. `GET /ai/food/quota` reports the
  `limit` that applies to the caller.
- **Daily reset at midnight Vietnam time** (Asia/Ho_Chi_Minh, UTC+7, no DST), the same calendar day the
  diary uses. Not a rolling 24 hours: the reset is the same moment for every user, and the 403 and
  `GET /ai/food/quota` both say when it is (`resetsAt`).
- Quota key is the device while anonymous. A signed-in call uses the **higher** of the device's and the
  account's used count **for that day**, and both are incremented. Signing up does not give a fresh trial on
  the same day: a device that used 3 and then signs in has 2 left (limit 5), not 5. The next day both start at 0.
  A signed-in call with no `X-Device-Id` is counted on the account alone.
- Premium is unlimited and never touches the counters.
- Applies to signed-in **free** users too: after 5 successes per method they get the 403 below.
- Only a **successful, non-empty** analysis consumes a trial. A 5xx, a provider failure, or a result with
  no ingredients does not.
- Buying Premium still requires login (unchanged).

## `POST /ai/food/analyze-image`

`multipart/form-data`: `image` (jpeg/png/heic/heif), optional `language` (`vi`|`en`, default `vi`).

## `POST /ai/food/analyze-text`

```json
{ "description": "a bowl of beef pho", "language": "vi", "inputMethod": "text" }
```

`inputMethod`: `"text"` (default) or `"voice"`. Voice is dictated text sent here; the field only selects which
counter is used.

Both return `200`:

```json
{ "mealName": "Pho", "ingredients": [ { "name": "beef", "quantityG": 200, "kcal": 300, "carbsG": 0,
  "proteinG": 40, "fatG": 15, "fiberG": null, "confidence": 0.9 } ], "imageUrl": null }
```

(`imageUrl` is set for `analyze-image` only.) The 200 body carries no quota; read it from `GET /ai/food/quota`.

## Trials used up: `403`

```json
{ "message": "free AI trials used up; Premium is required", "code": "ai_trial_exhausted",
  "inputMethod": "image", "resetsAt": "2026-10-02T00:00:00+07:00" }
```

Match on `code === "ai_trial_exhausted"`. `inputMethod` is `image`, `text`, or `voice`. `resetsAt` is an ISO 8601
timestamp with a `+07:00` offset: the next Vietnam midnight, when that method has its tries again. Other 403s do not
carry this code. (Not 402: `402` is the existing `premium_required` response for Premium-only features.)

## `GET /ai/food/quota`

Same identity rules as above. `200`:

```json
{ "unlimited": false,
  "resetsAt": "2026-10-02T00:00:00+07:00",
  "image": { "limit": 3, "remaining": 2 },
  "text":  { "limit": 3, "remaining": 3 },
  "voice": { "limit": 3, "remaining": 2 } }
```

(`limit` is 3 for a guest, 5 for a signed-in user.)

`remaining` is for today. Premium: `{ "unlimited": true, "resetsAt": null, "image": null, "text": null, "voice": null }`.

## Rate limits

Anonymous calls (no Bearer) are limited to **30 per hour per client IP**, counted on every attempt including
403s. Over the limit: **429** `{ "message": "too many requests, try again later" }`. The device id is
spoofable, so the IP limit is what bounds abuse. Signed-in calls skip it. The limit is per server process.

## Known limits

- A device can use up to 9 free analyses every day with no end date, and a spoofed device id restarts at 3
  per method; only the per-IP limit bounds that. A signed-in account gets up to 15 a day.
- Check-then-consume is not atomic: concurrent requests from one owner can overshoot the limit by a few.
- IPs behind a shared NAT share the 30/hour budget.
