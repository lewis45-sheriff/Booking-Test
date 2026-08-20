"""
Custom exception hierarchy for the clinic booking system.

All domain errors extend BookingSystemException. The DRF custom exception
handler maps each subclass to the appropriate HTTP status code and normalises
error responses to {"detail": "<message>"}.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response


class BookingSystemException(Exception):
    """Base class for all domain exceptions."""
    http_status: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------

class DoctorNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Doctor not found."


class PatientNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Patient not found."


class AppointmentNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Appointment not found."


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------

class SlotConflictError(BookingSystemException):
    http_status = 409
    default_message = "The requested slot is already booked."


class AppointmentAlreadyCancelledError(BookingSystemException):
    http_status = 409
    default_message = "The appointment is already cancelled."


class CancelledAppointmentRescheduleError(BookingSystemException):
    http_status = 409
    default_message = "Cancelled appointments cannot be rescheduled."


# ---------------------------------------------------------------------------
# 422 Unprocessable Entity
# ---------------------------------------------------------------------------

class SlotOutsideWorkingHoursError(BookingSystemException):
    http_status = 422
    default_message = "The slot falls outside the doctor's working hours."


class SlotNotAlignedError(BookingSystemException):
    http_status = 422
    default_message = "The slot must align to a 30-minute boundary (:00 or :30)."


class SlotInPastError(BookingSystemException):
    http_status = 422
    default_message = "Past slots cannot be booked."


class InsufficientLeadTimeError(BookingSystemException):
    http_status = 422
    default_message = "Booking requires at least 1 hour of lead time."


class InvalidCancellationReasonError(BookingSystemException):
    http_status = 422
    default_message = "Cancellation reason must be between 1 and 500 characters."


class InvalidWorkingHoursError(BookingSystemException):
    http_status = 422
    default_message = "Working hours start time must be before end time."


# ---------------------------------------------------------------------------
# DRF custom exception handler
# ---------------------------------------------------------------------------

def booking_exception_handler(exc, context):
    """
    Maps domain exceptions and DRF ValidationErrors to a uniform
    {"detail": "<string>"} JSON response.
    """
    # Handle our domain exceptions first
    if isinstance(exc, BookingSystemException):
        return Response({"detail": exc.message}, status=exc.http_status)

    # Fall back to DRF's default handler for ValidationError, NotFound, etc.
    response = exception_handler(exc, context)
    if response is not None:
        # Normalise DRF validation errors (list/dict format) to a single string
        detail = response.data.get("detail", response.data)
        if isinstance(detail, list):
            detail = " ".join(str(d) for d in detail)
        elif isinstance(detail, dict):
            detail = "; ".join(f"{k}: {v}" for k, v in detail.items())
        response.data = {"detail": str(detail)}
    return response
