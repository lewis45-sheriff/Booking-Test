"""Reschedule service — appointment rescheduling orchestration."""
# Implemented in Task 8.3

from __future__ import annotations

from datetime import date, datetime, time

from appointments.exceptions import (
    CancelledAppointmentRescheduleError,
    SlotOutsideWorkingHoursError,
)
from appointments.models import Appointment
from appointments.repositories.appointment_repo import AppointmentRepo
from appointments.repositories.doctor_repo import DoctorRepo
from appointments.services.booking import validate_booking_request


def reschedule_appointment(
    appointment_id,
    new_date: date,
    new_start_time: time,
    now: datetime = None,
) -> Appointment:
    """Reschedule an existing appointment to a new date/time slot.

    Parameters
    ----------
    appointment_id:
        Primary key of the appointment to reschedule.
    new_date:
        The new calendar date for the appointment.
    new_start_time:
        The new slot start time for the appointment.
    now:
        The current datetime used as the reference point for validation.
        Defaults to ``datetime.utcnow()`` if not provided.

    Returns
    -------
    Appointment
        The updated appointment instance with the new date and start time.

    Raises
    ------
    AppointmentNotFoundError
        If no appointment with the given ID exists.
    CancelledAppointmentRescheduleError
        If the appointment has already been cancelled.
    SlotOutsideWorkingHoursError
        If the doctor has no working hours configured for the new slot's day,
        or if the new slot falls outside those working hours.
    SlotInPastError
        If the new slot datetime is in the past.
    InsufficientLeadTimeError
        If the new slot is less than 60 minutes from now.
    SlotNotAlignedError
        If the new slot time is not aligned to a 30-minute boundary.
    SlotConflictError
        If the new slot is already booked for the same doctor.
    """
    # 1. Default now to UTC current time
    if now is None:
        now = datetime.utcnow()

    # 2. Look up appointment — raises AppointmentNotFoundError if missing
    appointment = AppointmentRepo().get_by_id(appointment_id)

    # 3. Reject rescheduling of cancelled appointments
    if appointment.status == Appointment.STATUS_CANCELLED:
        raise CancelledAppointmentRescheduleError()

    # 4. Determine the day of week for the new slot (0=Monday, 6=Sunday)
    day_of_week = new_date.weekday()

    # 5. Look up working hours for the doctor on the new slot's day
    working_hours = DoctorRepo().get_working_hours(appointment.doctor_id, day_of_week)
    if working_hours is None:
        raise SlotOutsideWorkingHoursError()

    # 6. Validate the new slot against working hours, lead time, alignment, etc.
    validate_booking_request(new_start_time, new_date, working_hours, now)

    # 7. Persist the new slot (frees original) — raises SlotConflictError on DB conflict
    updated_appointment = AppointmentRepo().reschedule(appointment, new_date, new_start_time)

    # 8. Return the updated appointment
    return updated_appointment
