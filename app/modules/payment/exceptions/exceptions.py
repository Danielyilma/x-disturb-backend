"""app/modules/payment/exceptions/exceptions.py — Payment domain exceptions."""

from app.core.base_exception import BaseExceptionError


class PlanNotFoundError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Subscription plan not found.", status_code=404)


class PlanInactiveError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Subscription plan is not currently active.", status_code=400)


class PaymentInitializationError(BaseExceptionError):
    def __init__(self, detail: str = "Payment initialization failed.") -> None:
        super().__init__(message=detail, status_code=502)


class PaymentVerificationError(BaseExceptionError):
    def __init__(self, detail: str = "Payment verification failed.") -> None:
        super().__init__(message=detail, status_code=502)


class TransactionNotFoundError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Transaction not found.", status_code=404)


class TransactionAlreadyProcessedError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(
            message="Transaction has already been processed.", status_code=409
        )


class ChapaNotConfiguredError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(
            message="Chapa payment gateway is not configured on this server.",
            status_code=503,
        )
