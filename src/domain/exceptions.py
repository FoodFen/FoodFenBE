"""Domain error hierarchy. Standard library only."""


class DomainException(Exception):
    """Base class for every domain-level error."""


class EntityNotFoundException(DomainException):
    """A requested entity does not exist."""


class UserNotFoundException(EntityNotFoundException):
    """A requested user does not exist."""


class UserAlreadyExistsException(DomainException):
    """A user with the same unique attribute (email) already exists."""


class InvalidUserAttributeException(DomainException):
    """A user attribute violates a domain invariant."""
