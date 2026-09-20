# Social sign-in

Companion to [`authentication.md`](./authentication.md) — read that first for
what a JWT is, why access+refresh tokens exist, and the camelCase/int-id/
failure-body conventions. This page covers only what's specific to
`POST /auth/social`: exchanging a Google or Apple identity token for the same
session shape `/auth/sign-in` returns.

## `POST /auth/social` — no auth required

```
Request:
  { "provider": "google" | "apple", "idToken": "string",
    "fullName": "string | undefined", "email": "string | undefined" }

Response 200: the same AuthSession shape as /auth/sign-in
Response 401: bad/expired/wrongly-audienced token
Response 400: no email could be determined (see §3)
```

`fullName` / `email` are **Apple-only**, and only ever present on the
account's *first-ever* authorization for this app — Apple does not resend
them on a later sign-in with the same Apple ID, and the client has no way to
resupply them later either. Google never sends them here at all: its ID
token already carries verified `name`/`email` claims.

## 1. Verifying the token — never trust the claims unchecked

`idToken` is a JWT the *provider* signed, not us. Before reading anything out
of it we must verify, against the provider's own current public keys:

1. **Signature** — was this actually signed by Google/Apple?
2. **Issuer** (`iss`) — is it `https://accounts.google.com` /
   `https://appleid.apple.com`, not some other signer?
3. **Audience** (`aud`) — was it issued *for this app* (our OAuth client id),
   not for someone else's app that happens to use the same provider?
4. **Expiry** (`exp`) — is it still valid?

`src/infrastructure/security/social_identity_verifier.py::JwtSocialIdentityVerifier`
does this with **PyJWT alone** — no new heavyweight dependency (no
`google-auth`). `jwt.PyJWKClient` fetches and caches each provider's JWKS
(public key set); `jwt.decode(..., algorithms=["RS256"])` checks the
signature and expiry. Issuer and audience are then checked **by hand**
against `GOOGLE_OAUTH_CLIENT_IDS` / `APPLE_CLIENT_IDS` (comma-separated env
vars — an app usually has more than one client id: iOS + Android, or a
bundle id plus a Sign In with Apple Service ID).

> **A real bug this caught in testing:** PyJWT refuses to decode *any* token
> that carries an `aud` claim unless you also pass `audience=` to `decode()`
> — even though we want to check audience ourselves, against a list. Every
> real Google/Apple token carries `aud`, so without
> `options={"verify_aud": False}`, every real sign-in would have failed
> before reaching our own check. Caught by
> `tests/unit/test_social_identity_verifier.py`, which signs real RS256
> tokens with a locally generated keypair and feeds them through a fake
> `PyJWKClient` — no network call, but the actual signature/issuer/audience
> logic runs for real, not mocked away.

**If a provider's client ids aren't configured, that provider fails
closed**: `RuntimeError` → uncaught → `500`. Not a silent "any audience is
fine" open door. Set `GOOGLE_OAUTH_CLIENT_IDS` / `APPLE_CLIENT_IDS` before
that provider will work at all.

## 2. Resolving the token to an account

```
SocialSignInUseCase:
  identity = verifier.verify(provider, idToken)   # subject, email, email_verified

  linked = social_identities.get_by_provider_subject(provider, identity.subject)
  if linked is not None:
      user = users.get_by_id(linked.user_id)      # returning user -> same account
      return issue_session(user)

  # first time we've seen this (provider, subject) pair
  email = body.email or identity.email
  if not email:  raise InvalidUserAttributeException     -> HTTP 400

  existing = users.get_by_email(email)
  if existing is not None:
      user = existing                              # <-- linking policy, see below
  else:
      user = User.create(email=email, name=body.fullName, password_hash=None)
      user.verify_email(now)                        # the provider already verified it
      user = users.create(user)

  social_identities.create(SocialIdentity(user_id=user.id, provider, identity.subject))
  return issue_session(user)
```

`social_identities` (migration `0006`) is what makes a *returning* sign-in
resolve to the same account: `(provider, provider_user_id)` is unique, where
`provider_user_id` is the token's verified `sub` claim — stable across
sign-ins, unlike an email a user could change.

### Linking policy

**If the verified email matches an existing password-based account, this
signs into that account** (auto-link) — chosen over rejecting the sign-in or
creating a duplicate, and the only one of the three that's actually possible
without a schema change: `users.email` is `UNIQUE`, and every email-keyed
flow in this API (sign-in, password-reset) depends on that.

This is deliberately permissive: proving control of a *provider-verified*
email is treated as good enough to use interchangeably with that email's
password. If that's ever too permissive for this product, the guard is one
`if` in `SocialSignInUseCase` — reject or route to a "link your accounts"
step. No client-side change needed either way; the client only ever sees a
returned session.

### New accounts are pre-verified, passwordless

A brand-new social account gets `password_hash=None` (there is no password —
sign-in is only ever via that provider, unless the account later goes through
`/auth/reset-password` to set one) and `email_verified_at` set immediately:
the provider already attests to the address, so there is no separate
verification email to send for this account.

## 3. The "no email" edge case

Google's ID token always carries `email` when the `email` scope was
requested (the normal case for `GoogleSignin`). Apple always returns an
email on `signInAsync()` — a real one, or a private-relay address if the
user chose to hide it (see below) — but **only on the first authorization**.
If neither the request body nor the verified token has an email — malformed
client integration, or an Apple client bug re-sending on a later sign-in
with nothing to send — there is no way to create or resolve an account:
`InvalidUserAttributeException` → `400`.

## 4. Apple private relay addresses

Apple can return an `@privaterelay.appleid.com` forwarding address instead
of the user's real one. This implementation does **not** treat it specially
— it's stored and used as the account's email exactly like any other
address (sign-in, password-reset emails, etc. all go through Apple's relay
transparently, which is the point of the feature). There is no metadata
field surfacing "this is a relay address" anywhere in this API; add one if a
product need for it shows up.

## 5. Configuration

| setting | env var | default |
|---|---|---|
| Google OAuth client ids | `GOOGLE_OAUTH_CLIENT_IDS` | empty (provider fails closed) |
| Apple client ids (bundle id / Service ID) | `APPLE_CLIENT_IDS` | empty (provider fails closed) |

Provisioning the actual OAuth client / Sign In with Apple Service ID in each
provider's console is an ops task, not something this doc can hand you.

## 6. What's deliberately not built here

| Left out | Why | When to revisit |
|---|---|---|
| Linking an *additional* provider onto an already-logged-in account | No such flow in the client contract | A "connect your Google account" settings screen would need its own endpoint |
| Un-linking a social identity | Same | Same |
| Surfacing "this account has no password" to a client that might try password sign-in for it | `LoginUseCase` already returns the same generic 401 either way (no password hash to check against) | If a client wants to show "sign in with Google instead" |
| Rate limiting / abuse prevention on this endpoint | Same as every other endpoint in this API | Whenever the rest of the API gets it |
