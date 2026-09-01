"""Application exception types."""


class AppError(Exception):
    """Base application error."""

    status_code: int = 500
    message: str = "Internal Server Error"

    def __init__(self, message: str | None = None):
        """Override default message if provided."""
        self.message = message or self.__class__.message
        super().__init__(self.message)


class BadRequestError(AppError):
    """400 error."""

    status_code = 400
    message = "Bad Request"


class UnauthorizedError(AppError):
    """401 error."""

    status_code = 401
    message = "Unauthorized"


class ForbiddenError(AppError):
    """403 error."""

    status_code = 403
    message = "Forbidden"


class NotFoundError(AppError):
    """404 error."""

    status_code = 404
    message = "Not Found"


class ConflictError(AppError):
    """409 error."""

    status_code = 409
    message = "Conflict"


class TooManyRequestsError(AppError):
    """429 error."""

    status_code = 429
    message = "Too Many Requests"
