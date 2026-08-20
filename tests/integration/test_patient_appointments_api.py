"""
Integration tests for GET /patients/{patient_id}/appointments — Patient Appointments API.

Tests run against the actual Django stack using DRF's APIClient.
"""
import uuid
from datetime import date, time, timedelta

import pytest

from appointments.models import Appointment, Doctor, Patient, WorkingHours


def _next_weekday_far_future():
    """Return the next weekday (Mon-Fri) that is at least 8 days from today."""
    today = date.today()
    candidate = today + timedelta(days=8)
    while candidate.weekday() > 4:
        candidate += timedelta(days=1)
    return candidate


@pytest.fixture
def pa_doctor(db):
    """Doctor for patient-appointments tests."""
    return Doctor.objects.create(name="Dr. PatientList", specialty="Testing")


@pytest.fixture
def pa_patient(db):
    """Patient for patient-appointments tests."""
    return Patient.objects.create(
        name="PA Patient",
        email=f"pa-{uuid.uuid4().hex[:8]}@test.com",
        phone="555-0400",
    )


@pytest.fixture
def pa_working_hours(db, pa_doctor):
    """Working hours Mon-Fri 09:00-17:00 for pa_doctor."""
    hours = []
    for day in range(5):
        wh = WorkingHours.objects.create(
            doctor=pa_doctor,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        hours.append(wh)
    return hours


@pytest.mark.django_db
class TestPatientAppointmentsSuccess:
    def test_patient_appointments_returns_upcoming(
        self, api_client, pa_doctor, pa_patient, pa_working_hours
    ):
        """Patient with scheduled future appointment → returns list with expected fields."""
        future_weekday = _next_weekday_far_future()
        Appointment.objects.create(
            doctor=pa_doctor,
            patient=pa_patient,
            appointment_date=future_weekday,
            start_time=time(10, 0),
            status=Appointment.STATUS_SCHEDULED,
        )

        response = api_client.get(f"/patients/{pa_patient.id}/appointments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        appt = data[0]
        assert "id" in appt
        assert appt["doctor_name"] == "Dr. PatientList"
        assert appt["appointment_date"] == future_weekday.isoformat()
        assert appt["start_time"] in ("10:00", "10:00:00")
        assert appt["status"] == "scheduled"

    def test_patient_appointments_empty_no_upcoming(
        self, api_client, pa_patient
    ):
        """Patient with no appointments → empty list 200."""
        response = api_client.get(f"/patients/{pa_patient.id}/appointments")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_patient_appointments_excludes_cancelled(
        self, api_client, pa_doctor, pa_patient, pa_working_hours
    ):
        """Cancelled appointment not in results."""
        future_weekday = _next_weekday_far_future()
        Appointment.objects.create(
            doctor=pa_doctor,
            patient=pa_patient,
            appointment_date=future_weekday,
            start_time=time(11, 0),
            status=Appointment.STATUS_CANCELLED,
            cancellation_reason="Test cancellation",
        )

        response = api_client.get(f"/patients/{pa_patient.id}/appointments")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_patient_appointments_50_cap(
        self, api_client, pa_doctor, pa_patient, pa_working_hours
    ):
        """Only nearest 50 returned when > 50 exist."""
        base_date = _next_weekday_far_future()

        # Create 55 appointments on different future dates
        for i in range(55):
            appt_date = base_date + timedelta(days=i * 7)  # weekly intervals
            # Make sure it's a weekday
            while appt_date.weekday() > 4:
                appt_date += timedelta(days=1)
            Appointment.objects.create(
                doctor=pa_doctor,
                patient=pa_patient,
                appointment_date=appt_date,
                start_time=time(10, 0),
                status=Appointment.STATUS_SCHEDULED,
            )

        response = api_client.get(f"/patients/{pa_patient.id}/appointments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50


@pytest.mark.django_db
class TestPatientAppointmentsErrors:
    def test_patient_appointments_404_not_found(self, api_client):
        """Non-existent patient → 404."""
        response = api_client.get(f"/patients/{uuid.uuid4()}/appointments")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
