"""
Integration tests for PATCH /appointments/{id}/cancel — Cancellation API.

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
def scheduled_appointment(db):
    """Create a scheduled appointment for cancellation tests."""
    doctor = Doctor.objects.create(name="Dr. Cancel", specialty="Testing")
    patient = Patient.objects.create(
        name="Cancel Patient",
        email=f"cancel-{uuid.uuid4().hex[:8]}@test.com",
        phone="555-0200",
    )
    future_weekday = _next_weekday_far_future()
    # Create working hours for that day
    WorkingHours.objects.create(
        doctor=doctor,
        day_of_week=future_weekday.weekday(),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    appointment = Appointment.objects.create(
        doctor=doctor,
        patient=patient,
        appointment_date=future_weekday,
        start_time=time(10, 0),
        status=Appointment.STATUS_SCHEDULED,
    )
    return appointment


@pytest.mark.django_db
class TestCancellationSuccess:
    def test_cancel_success(self, api_client, scheduled_appointment):
        """Cancel a scheduled appointment with valid reason → 200, status=cancelled."""
        response = api_client.patch(
            f"/appointments/{scheduled_appointment.id}/cancel",
            {"cancellation_reason": "Patient is feeling better"},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["cancellation_reason"] == "Patient is feeling better"


@pytest.mark.django_db
class TestCancellationErrors:
    def test_cancel_404_not_found(self, api_client):
        """Non-existent appointment → 404."""
        response = api_client.patch(
            f"/appointments/{uuid.uuid4()}/cancel",
            {"cancellation_reason": "Some reason"},
            format="json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_cancel_409_already_cancelled(self, api_client, scheduled_appointment):
        """Cancel same appointment twice → 409 on second attempt."""
        # First cancellation should succeed
        response1 = api_client.patch(
            f"/appointments/{scheduled_appointment.id}/cancel",
            {"cancellation_reason": "First cancellation"},
            format="json",
        )
        assert response1.status_code == 200

        # Second cancellation should conflict
        response2 = api_client.patch(
            f"/appointments/{scheduled_appointment.id}/cancel",
            {"cancellation_reason": "Second attempt"},
            format="json",
        )

        assert response2.status_code == 409
        data = response2.json()
        assert "detail" in data

    def test_cancel_422_missing_reason(self, api_client, scheduled_appointment):
        """No body/empty reason → validation error (400 from DRF serializer)."""
        response = api_client.patch(
            f"/appointments/{scheduled_appointment.id}/cancel",
            {},
            format="json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_cancel_422_reason_too_long(self, api_client, scheduled_appointment):
        """Reason > 500 chars → validation error (400 from DRF serializer)."""
        long_reason = "x" * 501

        response = api_client.patch(
            f"/appointments/{scheduled_appointment.id}/cancel",
            {"cancellation_reason": long_reason},
            format="json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
