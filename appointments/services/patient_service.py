"""Patient-focused service orchestration."""

from __future__ import annotations

from datetime import datetime

from appointments.exceptions import PatientNotFoundError  # noqa: F401 (re-exported for callers)
from appointments.repositories.appointment_repo import AppointmentRepo
from appointments.repositories.patient_repo import PatientRepo


def list_upcoming_appointments(patient_id, now: datetime = None):
    """Return upcoming scheduled appointments for a patient.

    Args:
        patient_id: UUID (or string representation) of the patient.
        now: Reference datetime. Defaults to ``datetime.utcnow()`` when not
             supplied.

    Returns:
        A queryset of :class:`~appointments.models.Appointment` instances,
        ordered by ``(appointment_date, start_time)``, limited to at most 50
        rows.

    Raises:
        PatientNotFoundError: if no patient with *patient_id* exists.
    """
    if now is None:
        now = datetime.utcnow()

    # Raises PatientNotFoundError if the patient does not exist.
    PatientRepo().get_by_id(patient_id)

    return AppointmentRepo().list_upcoming_for_patient(patient_id, now)
