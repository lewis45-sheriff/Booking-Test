"""Repository for Appointment data access."""

from datetime import date, datetime, time

from django.db import IntegrityError
from django.db.models import Q

from appointments.exceptions import AppointmentNotFoundError, SlotConflictError
from appointments.models import Appointment


class AppointmentRepo:
    """Data-access layer for the Appointment model.

    All public methods are intentionally free of business-logic so that
    services can compose them without coupling to ORM details.
    """

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_by_id(self, appointment_id) -> Appointment:
        """Return the Appointment with the given PK.

        Raises:
            AppointmentNotFoundError: if no matching row exists.
        """
        try:
            return Appointment.objects.get(pk=appointment_id)
        except Appointment.DoesNotExist:
            raise AppointmentNotFoundError()

    def get_booked_slots(self, doctor_id, appointment_date: date) -> list[time]:
        """Return start times of non-cancelled appointments for a doctor on a date.

        Args:
            doctor_id: UUID of the doctor.
            appointment_date: The calendar date to query.

        Returns:
            A list of :class:`datetime.time` objects representing the
            start times of all *scheduled* appointments.
        """
        qs = Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            status=Appointment.STATUS_SCHEDULED,
        )
        return list(qs.values_list("start_time", flat=True))

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create(
        self,
        doctor_id,
        patient_id,
        appointment_date: date,
        start_time: time,
    ) -> Appointment:
        """Persist a new appointment and return the saved ORM object.

        Args:
            doctor_id: UUID of the doctor.
            patient_id: UUID of the patient.
            appointment_date: The calendar date of the appointment.
            start_time: The start time of the 30-minute slot.

        Returns:
            The newly created :class:`~appointments.models.Appointment` instance.

        Raises:
            SlotConflictError: if the DB unique constraint on
                ``(doctor_id, appointment_date, start_time)`` fires,
                indicating the slot is already booked.
        """
        try:
            return Appointment.objects.create(
                doctor_id=doctor_id,
                patient_id=patient_id,
                appointment_date=appointment_date,
                start_time=start_time,
                status=Appointment.STATUS_SCHEDULED,
            )
        except IntegrityError:
            raise SlotConflictError()

    def cancel(self, appointment: Appointment, reason: str) -> Appointment:
        """Mark an appointment as cancelled and record the reason.

        Args:
            appointment: The :class:`~appointments.models.Appointment` to cancel.
            reason: A non-empty string describing the cancellation reason.

        Returns:
            The updated appointment instance (already saved).
        """
        appointment.status = Appointment.STATUS_CANCELLED
        appointment.cancellation_reason = reason
        appointment.save()
        return appointment

    def reschedule(
        self,
        appointment: Appointment,
        new_date: date,
        new_start_time: time,
    ) -> Appointment:
        """Move an appointment to a new date/time slot.

        Args:
            appointment: The :class:`~appointments.models.Appointment` to reschedule.
            new_date: The new calendar date.
            new_start_time: The new slot start time.

        Returns:
            The updated appointment instance (already saved).

        Raises:
            SlotConflictError: if the DB unique constraint fires on the new slot.
        """
        appointment.appointment_date = new_date
        appointment.start_time = new_start_time
        try:
            appointment.save()
        except IntegrityError:
            raise SlotConflictError()
        return appointment

    def list_upcoming_for_patient(
        self,
        patient_id,
        now: datetime,
        limit: int = 50,
    ):
        """Return upcoming scheduled appointments for a patient.

        "Upcoming" means *strictly after* ``now``: either the appointment
        date is in the future, or it is today and the start time is after
        the current time-of-day.

        Args:
            patient_id: UUID of the patient.
            now: The reference datetime (server time).
            limit: Maximum number of results to return (default 50).

        Returns:
            A Django queryset of :class:`~appointments.models.Appointment`
            instances ordered by ``(appointment_date, start_time)`` and
            capped at ``limit`` rows.
        """
        future_filter = Q(appointment_date__gt=now.date()) | Q(
            appointment_date=now.date(),
            start_time__gt=now.time(),
        )
        return (
            Appointment.objects.filter(
                patient_id=patient_id,
                status=Appointment.STATUS_SCHEDULED,
            )
            .filter(future_filter)
            .order_by("appointment_date", "start_time")[:limit]
        )
