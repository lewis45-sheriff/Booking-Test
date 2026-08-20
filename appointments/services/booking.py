"""Booking service — slot validation and booking creation."""
# Implemented in Tasks 5.1 and 8.1

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from appointments.exceptions import (
    InsufficientLeadTimeError,
    SlotConflictError,
    SlotInPastError,
    SlotNotAlignedError,
    SlotOutsideWorkingHoursError,
)
from appointments.models import Appointment
from appointments.repositories.appointment_repo import AppointmentRepo
from appointments.repositories.doctor_repo import DoctorRepo
from appointments.repositories.patient_repo import PatientRepo
from appointments.services.availability import WorkingHoursConfig, _time_to_minutes

_SLOT_MINUTES = 30


def validate_booking_request(
    slot_time: time,
    slot_date: date,
    working_hours,
    now: datetime,
) -> None:
    """Validate a booking request, raising a domain exception on any violation.

    Validation is applied in the following order:

    1. **Past check** — the slot datetime must be strictly after *now*.
    2. **Lead-time check** — the slot datetime must be at least 60 minutes
       after *now*.
    3. **Working-hours check** — *working_hours* must be configured and the
       slot time must fall within ``[start_time, end_time)``.
    4. **Alignment check** — the slot minute must be 0 or 30.
    5. **Fit check** — the complete 30-minute slot must end on or before
       ``working_hours.end_time`` (i.e. ``slot_time + 30 min ≤ end_time``).

    Parameters
    ----------
    slot_time:
        The requested start time of the appointment slot.
    slot_date:
        The requested date of the appointment.
    working_hours:
        An object with ``.start_time`` and ``.end_time`` :class:`~datetime.time`
        attributes (e.g. :class:`~appointments.services.availability.WorkingHoursConfig`
        or the ``WorkingHours`` Django ORM model), or ``None`` when the doctor
        has no working hours configured for that day.
    now:
        The current datetime used as the reference point for past / lead-time
        checks.  Should be timezone-naive and consistent with *slot_date* /
        *slot_time* (i.e. all in the same timezone, typically UTC).

    Raises
    ------
    SlotInPastError
        If ``datetime.combine(slot_date, slot_time) <= now``.
    InsufficientLeadTimeError
        If the slot is in the future but less than 60 minutes away from *now*.
    SlotOutsideWorkingHoursError
        If *working_hours* is ``None``, ``slot_time < working_hours.start_time``,
        ``slot_time >= working_hours.end_time``, or the 30-minute slot does not
        fit entirely within working hours.
    SlotNotAlignedError
        If ``slot_time.minute`` is not 0 or 30.
    """
    slot_dt = datetime.combine(slot_date, slot_time)

    # 1. Past check
    if slot_dt <= now:
        raise SlotInPastError()

    # 2. Lead-time check (must be at least 60 min in the future)
    if slot_dt < now + timedelta(hours=1):
        raise InsufficientLeadTimeError()

    # 3. Working-hours check
    if working_hours is None:
        raise SlotOutsideWorkingHoursError()

    if slot_time < working_hours.start_time or slot_time >= working_hours.end_time:
        raise SlotOutsideWorkingHoursError()

    # 4. Alignment check (must be on the :00 or :30 boundary)
    if slot_time.minute not in (0, 30):
        raise SlotNotAlignedError()

    # 5. Fit check — the complete 30-min slot must end at or before end_time
    slot_end_minutes = _time_to_minutes(slot_time) + _SLOT_MINUTES
    end_minutes = _time_to_minutes(working_hours.end_time)
    if slot_end_minutes > end_minutes:
        raise SlotOutsideWorkingHoursError()


def create_booking(
    doctor_id,
    patient_id,
    appointment_date: date,
    start_time: time,
    now: datetime = None,
) -> Appointment:
    """Orchestrate the full booking flow: look up doctor/patient, validate the
    requested slot against working hours and business rules, check for conflicts,
    and persist the appointment.

    Parameters
    ----------
    doctor_id:
        UUID (or PK) of the doctor.
    patient_id:
        UUID (or PK) of the patient.
    appointment_date:
        The requested date of the appointment.
    start_time:
        The requested start time of the 30-minute slot.
    now:
        Reference datetime for past / lead-time checks.  Defaults to
        ``datetime.utcnow()`` when not provided.

    Returns
    -------
    Appointment
        The newly created :class:`~appointments.models.Appointment` instance.

    Raises
    ------
    DoctorNotFoundError
        If no doctor with *doctor_id* exists.
    PatientNotFoundError
        If no patient with *patient_id* exists.
    SlotOutsideWorkingHoursError
        If the doctor has no working hours configured for the requested day,
        or if the slot falls outside those hours.
    SlotInPastError
        If the requested slot datetime is in the past.
    InsufficientLeadTimeError
        If the slot is fewer than 60 minutes from *now*.
    SlotNotAlignedError
        If the slot time is not on a 30-minute boundary.
    SlotConflictError
        If the slot is already booked (application-level check or DB constraint).
    """
    if now is None:
        now = datetime.utcnow()

    # Step 1 — look up doctor (raises DoctorNotFoundError if absent)
    DoctorRepo().get_by_id(doctor_id)

    # Step 2 — look up patient (raises PatientNotFoundError if absent)
    PatientRepo().get_by_id(patient_id)

    # Step 3 — determine day of week (0 = Monday)
    day_of_week = appointment_date.weekday()

    # Step 4 — look up working hours; raise SlotOutsideWorkingHoursError if none
    working_hours = DoctorRepo().get_working_hours(doctor_id, day_of_week)
    if working_hours is None:
        raise SlotOutsideWorkingHoursError()

    # Step 5 — validate booking request (raises SlotInPastError,
    #           InsufficientLeadTimeError, SlotOutsideWorkingHoursError,
    #           or SlotNotAlignedError as appropriate)
    validate_booking_request(start_time, appointment_date, working_hours, now)

    # Step 6 — persist (raises SlotConflictError on DB unique-constraint violation)
    appointment = AppointmentRepo().create(
        doctor_id, patient_id, appointment_date, start_time
    )

    # Step 7 — return the created appointment
    return appointment
