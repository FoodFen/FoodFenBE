"""Domain error hierarchy. Standard library only."""


class DomainException(Exception):
    """Base class for every domain-level error."""


class EntityNotFoundException(DomainException):
    """A requested entity does not exist."""


class UserNotFoundException(EntityNotFoundException):
    """A requested user does not exist."""


class UserAlreadyExistsException(DomainException):
    """A user with the same unique attribute (email) already exists."""


class InvalidAttributeException(DomainException):
    """An entity attribute violates a domain invariant."""


class InvalidUserAttributeException(InvalidAttributeException):
    """A user attribute violates a domain invariant."""


class UnreadableImageException(InvalidAttributeException):
    """An uploaded image is not a supported/decodable format."""


class WeakPasswordException(InvalidUserAttributeException):
    """A proposed password does not meet the strength policy."""


class AuthenticationException(DomainException):
    """Authentication failed. Maps to HTTP 401."""


class InvalidCredentialsException(AuthenticationException):
    """Email and password did not match an active account."""


class InvalidTokenException(AuthenticationException):
    """A token is missing, malformed, expired, or revoked."""


class PaymentNotFoundException(EntityNotFoundException):
    """A requested payment does not exist."""


class InvalidPaymentStateException(InvalidAttributeException):
    """An operation is not valid for a payment's current status."""


class InvalidWebhookSignatureException(AuthenticationException):
    """A webhook payload's signature does not match the expected checksum."""


class PremiumRequiredException(DomainException):
    """The user does not have an active Premium subscription. Maps to HTTP 402."""


class FoodEntryNotFoundException(EntityNotFoundException):
    """A requested food entry does not exist."""


class ActivityLogNotFoundException(EntityNotFoundException):
    """A requested activity log does not exist."""


class WaterLogNotFoundException(EntityNotFoundException):
    """A requested water log does not exist."""


class InsufficientCoinsException(DomainException):
    """The coin balance can't cover the requested spend. Maps to HTTP 409."""
