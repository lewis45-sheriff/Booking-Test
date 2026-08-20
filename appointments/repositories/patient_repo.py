"""Repository for Patient data access."""
from appointments.models import Patient
from appointments.exceptions import PatientNotFoundError


class PatientRepo:
    """Data access layer for Patient records."""

    def get_by_id(self, patient_id) -> Patient:
        """
        Retrieve a Patient by primary key.

        Raises:
            PatientNotFoundError: if no Patient with the given ID exists.
        """
        try:
            return Patient.objects.get(pk=patient_id)
        except Patient.DoesNotExist:
            raise PatientNotFoundError()
