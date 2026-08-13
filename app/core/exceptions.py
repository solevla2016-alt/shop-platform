class AppError(Exception):
    status_code: int = 500
    message: str = "Internal Server Error"

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    message = "Bad Request"


class UnauthorizedError(AppError):
    status_code = 401
    message = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    message = "Forbidden"


class NotFoundError(AppError):
    status_code = 404
    message = "Not Found"


class ConflictError(AppError):
    status_code = 409
    message = "Conflict"