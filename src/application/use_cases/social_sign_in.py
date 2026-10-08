"""Exchange a verified Google/Apple identity for a session.

Resolution order:
1. A ``SocialIdentity`` already links this exact (provider, subject) to a
   user — the common case for a returning user. Sign in to that account.
2. First time we've seen this (provider, subject): if the verified email
   matches an existing password account, **link** to it (auto-link, chosen
   over rejecting or creating a duplicate — the latter isn't possible anyway
   since ``users.email`` is unique). Otherwise create a new, passwordless
   account. Either way, record the ``SocialIdentity`` so next time is case 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.auth import AuthSessionDTO, SocialSignInInputDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.social_identity_repository import SocialIdentityRepositoryProtocol
from src.application.ports.social_identity_verifier import SocialIdentityVerifierProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.token_pair import issue_session
from src.domain.entities.social_identity import SocialIdentity
from src.domain.entities.user import User
from src.domain.exceptions import InvalidUserAttributeException, UserNotFoundException


@dataclass
class SocialSignInUseCase:
    users: UserRepositoryProtocol
    social_identities: SocialIdentityRepositoryProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol
    verifier: SocialIdentityVerifierProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: SocialSignInInputDTO) -> AuthSessionDTO:
        identity = self.verifier.verify(data.provider, data.id_token)

        linked = await self.social_identities.get_by_provider_subject(
            data.provider, identity.subject
        )
        if linked is not None:
            user = await self.users.get_by_id(linked.user_id)
            if user is None:
                raise UserNotFoundException(f"user {linked.user_id} not found")
            return await issue_session(user, self.tokens, self.refresh_tokens)

        # Only the provider-verified email counts: a client-supplied one would let any valid
        # token be pointed at someone else's account (auto-link below).
        email = (identity.email or "").strip().lower()
        if not email or not identity.email_verified:
            raise InvalidUserAttributeException(
                "social sign-in did not provide a verified email address"
            )

        user = await self.users.get_by_email(email)
        if user is None:
            user = User.create(email=email, name=data.full_name)
            user.verify_email(datetime.now(UTC))  # provider already verified this address
            user = await self.users.create(user)
        elif not user.is_email_verified:
            # Sign-up never gates on email verification, so an existing,
            # unverified account for this address may belong to someone who
            # registered it without owning it. The provider has now proven
            # real ownership — invalidate any password credential so a
            # squatter can no longer sign in, and record the verification.
            user.password_hash = None
            user.verify_email(datetime.now(UTC))
            user = await self.users.update(user)

        await self.social_identities.create(
            SocialIdentity.create(
                user_id=user.id, provider=data.provider, provider_user_id=identity.subject
            )
        )
        return await issue_session(user, self.tokens, self.refresh_tokens)
