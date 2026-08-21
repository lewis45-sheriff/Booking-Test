"""
Integration tests for PATCH /appointments/{id}/reschedule — Reschedule API.

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


def _second_weekday_far_future():
    """Return a second weekday at least 1 day after _next_weekday_far_future."""
    first = _next_weekday_far_future()
    candidate = first + timedelta(days=1)
    while candidate.weekday() > 4:
        candidate += timedelta(days=1)
    return candidate


@pytest.fixture
def reschedule_doctor(db):
    """Doctor for reschedule tests."""
    return Doctor.objects.create(name="Dr. Reschedule", specialty="Testing")


@pytest.fixture
def reschedule_patient(db):
    """Patient for reschedule tests."""
    return Patient.objects.create(
        name="Reschedule Patient",
        email=f"resched-{uuid.uuid4().hex[:8]}@test.com",
        phone="555-0300",
    )


@pytest.fixture
def reschedule_working_hours(db, reschedule_doctor):
    """Working hours Mon-Fri 09:00-17:00 for reschedule doctor."""
    hours = []
    for day in range(5):
        wh = WorkingHours.objects.create(
            doctor=reschedule_doctor,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        hours.append(wh)
    return hours


@pytest.fixture
def reschedule_appointment(db, reschedule_doctor, reschedule_patient, reschedule_working_hours):
    """Scheduled appointment for reschedule tests."""
    future_weekday = _next_weekday_far_future()
    return Appointment.objects.create(
        doctor=reschedule_doctor,
        patient=reschedule_patient,
        appointment_date=future_weekday,
        start_time=time(10, 0),
        status=Appointment.STATUS_SCHEDULED,
    )


@pytest.mark.django_db
class TestRescheduleSuccess:
    def test_reschedule_success(self, api_client, reschedule_appointment, reschedule_working_hours):
        """Move to a different valid slot → 200."""
        new_date = _second_weekday_far_future()

        response = api_client.patch(
            f"/appointments/{reschedule_appointment.id}/reschedule",
            {
                "appointment_date": new_date.isoformat(),
                "start_time": "14:00",
            },
            format="json",
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["appointment_date"] == new_date.isoformat()
        assert data["start_time"] in ("14:00", "14:00:00")
        assert data["status"] == "scheduled"


@pytest.mark.django_db
class TestRescheduleErrors:
    def test_reschedule_404_not_found(self, api_client):
        """Non-existent appointment → 404."""
        new_date = _next_weekday_far_future()

        response = api_client.patch(
            f"/appointments/{uuid.uuid4()}/reschedule",
            {
                "appointment_date": new_date.isoformat(),
                "start_time": "11:00",
            },
            format="json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_reschedule_409_cancelled(
        self, api_client, reschedule_appointment, reschedule_working_hours
    ):
        """Reschedule a cancelled appointment → 409."""
        # Cancel the appointment first
        reschedule_appointment.status = Appointment.STATUS_CANCELLED
        reschedule_appointment.cancellation_reason = "No longer needed"
        reschedule_appointment.save()

        new_date = _second_weekday_far_future()

        response = api_client.patch(
            f"/appointments/{reschedule_appointment.id}/reschedule",
            {
                "appointment_date": new_date.isoformat(),
                "start_time": "14:00",
            },
            format="json",
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    def test_reschedule_409_conflict(
        self, api_client, reschedule_doctor, reschedule_patient, reschedule_working_hours
    ):
        """New slot already taken → 409."""
        target_date = _second_weekday_far_future()

        # Create an existing appointment occupying the target slot
        Appointment.objects.create(
            doctor=reschedule_doctor,
            patient=reschedule_patient,
            appointment_date=target_date,
            start_time=time(14, 0),
            status=Appointment.STATUS_SCHEDULED,
        )

        # Create another appointment to reschedule
        source_date = _next_weekday_far_future()
        appt_to_move = Appointment.objects.create(
            doctor=reschedule_doctor,
            patient=reschedule_patient,
            appointment_date=source_date,
            start_time=time(11, 0),
            status=Appointment.STATUS_SCHEDULED,
        )

        response = api_client.patch(
            f"/appointments/{appt_to_move.id}/reschedule",
            {
                "appointment_date": target_date.isoformat(),
                "start_time": "14:00",
            },
            format="json",
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    def test_reschedule_422_outside_hours(
        self, api_client, reschedule_appointment, reschedule_working_hours
    ):
        """New slot outside working hours → 422."""
        new_date = _second_weekday_far_future()

        response = api_client.patch(
            f"/appointments/{reschedule_appointment.id}/reschedule",
            {
                "appointment_date": new_date.isoformat(),
                "start_time": "07:00",  # Before 09:00 start
            },
            format="json",
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_reschedule_422_past_slot(
        self, api_client, reschedule_appointment, reschedule_working_hours
    ):
        """New slot in the past → 422."""
        past_date = date(2020, 1, 6)  # A Monday well in the past

        response = api_client.patch(
            f"/appointments/{reschedule_appointment.id}/reschedule",
            {
                "appointment_date": past_date.isoformat(),
                "start_time": "10:00",
            },
            format="json",
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
