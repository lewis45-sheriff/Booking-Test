"""Cancellation service — appointment cancellation orchestration."""

from appointments.exceptions import AppointmentAlreadyCancelledError
from appointments.models import Appointment
from appointments.repositories.appointment_repo import AppointmentRepo


def cancel_appointment(appointment_id, cancellation_reason: str) -> Appointment:
    """Cancel an existing appointment.

    Args:
        appointment_id: The PK of the appointment to cancel.
        cancellation_reason: A non-empty string (1–500 chars) describing the reason.

    Returns:
        The updated :class:`~appointments.models.Appointment` instance with
        status set to ``"cancelled"`` and the reason recorded.

    Raises:
        AppointmentNotFoundError: if no appointment with ``appointment_id`` exists.
        AppointmentAlreadyCancelledError: if the appointment is already cancelled.
    """
    appointment = AppointmentRepo().get_by_id(appointment_id)

    if appointment.status == Appointment.STATUS_CANCELLED:
        raise AppointmentAlreadyCancelledError()

    AppointmentRepo().cancel(appointment, cancellation_reason)

    return appointment
