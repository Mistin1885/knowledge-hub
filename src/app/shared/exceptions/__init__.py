class AppError(Exception):
    """Base application error, mapped to an HTTP status by the API layer."""

    status_code = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404


class PermissionDeniedError(AppError):
    status_code = 403


class UnauthenticatedError(AppError):
    status_code = 401


class ConflictError(AppError):
    status_code = 409


class ValidationFailedError(AppError):
    status_code = 422
