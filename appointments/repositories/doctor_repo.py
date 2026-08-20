"""Repository for Doctor and WorkingHours data access."""
from appointments.models import Doctor, WorkingHours
from appointments.exceptions import DoctorNotFoundError


class DoctorRepo:
    """Data access layer for Doctor and WorkingHours records."""

    def get_by_id(self, doctor_id) -> Doctor:
        """
        Retrieve a Doctor by primary key.

        Raises:
            DoctorNotFoundError: if no Doctor with the given ID exists.
        """
        try:
            return Doctor.objects.get(pk=doctor_id)
        except Doctor.DoesNotExist:
            raise DoctorNotFoundError()

    def get_working_hours(self, doctor_id, day_of_week) -> WorkingHours | None:
        """
        Retrieve the WorkingHours for a doctor on a given day of the week.

        Args:
            doctor_id: UUID of the doctor.
            day_of_week: Integer 0–6 (0=Monday, 6=Sunday).

        Returns:
            WorkingHours instance if configured, otherwise None.
        """
        return WorkingHours.objects.filter(
            doctor_id=doctor_id, day_of_week=day_of_week
        ).first()
