"""Domain errors mapped to HTTP responses in the API layer."""


class AstraError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DuplicateEmailError(AstraError):
    pass


class DuplicatePhoneError(AstraError):
    pass


class InvalidCredentialsError(AstraError):
    pass


class PlaceNotFoundError(AstraError):
    pass


class AmbiguousPlaceError(AstraError):
    def __init__(self, message: str, candidates: list[dict]):
        super().__init__(message)
        self.candidates = candidates


class FutureBirthError(AstraError):
    pass


class BirthDetailsRequiredError(AstraError):
    pass


class KundaliNotFoundError(AstraError):
    pass


class ChartCalculationError(AstraError):
    pass


class PasswordReuseError(AstraError):
    pass
