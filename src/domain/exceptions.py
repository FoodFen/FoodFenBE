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


class WeakPasswordException(InvalidUserAttributeException):
    """A proposed password does not meet the strength policy."""


class AuthenticationException(DomainException):
    """Authentication failed. Maps to HTTP 401."""


class InvalidCredentialsException(AuthenticationException):
    """Email and password did not match an active account."""


class InvalidTokenException(AuthenticationException):
    """A token is missing, malformed, expired, or revoked."""
