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

- 3 successful analyses per input method: `image`, `text`, `voice`. Three independent counters.
- Counters are **lifetime**; they never reset.
- Quota key is the device while anonymous. A signed-in call uses the **higher** of the device's and the
  account's used count, and both are incremented. Signing up therefore does not give a fresh trial.
  A signed-in call with no `X-Device-Id` is counted on the account alone.
- Premium is unlimited and never touches the counters.
- Applies to signed-in **free** users too: after 3 successes per method they get the 403 below.
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
{ "message": "free AI trials used up; Premium is required", "code": "ai_trial_exhausted", "inputMethod": "image" }
```

Match on `code === "ai_trial_exhausted"`. `inputMethod` is `image`, `text`, or `voice`. Other 403s do not
carry this code. (Not 402: `402` is the existing `premium_required` response for Premium-only features.)

## `GET /ai/food/quota`

Same identity rules as above. `200`:

```json
{ "unlimited": false,
  "image": { "limit": 3, "remaining": 2 },
  "text":  { "limit": 3, "remaining": 3 },
  "voice": { "limit": 3, "remaining": 2 } }
```

Premium: `{ "unlimited": true, "image": null, "text": null, "voice": null }`.

## Rate limits

Anonymous calls (no Bearer) are limited to **30 per hour per client IP**, counted on every attempt including
403s. Over the limit: **429** `{ "message": "too many requests, try again later" }`. The device id is
spoofable, so the IP limit is what bounds abuse. Signed-in calls skip it. The limit is per server process.

## Known limits

- Check-then-consume is not atomic: concurrent requests from one owner can overshoot the 3 by a few.
- IPs behind a shared NAT share the 30/hour budget.
