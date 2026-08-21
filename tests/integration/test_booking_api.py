"""
Integration tests for POST /appointments — Booking API.

Tests run against the actual Django stack using DRF's APIClient.
"""
import uuid
from datetime import date, time, timedelta
from unittest.mock import patch

import pytest

from appointments.models import Appointment


def _next_weekday_far_future():
    """Return the next Monday that is > 7 days from today."""
    today = date.today()
    # Find next Monday
    days_ahead = 7 - today.weekday()  # 0=Monday
    if days_ahead <= 7:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


@pytest.mark.django_db
class TestBookingSuccess:
    def test_booking_success_returns_201(self, api_client, doctor, patient, working_hours):
        """Valid booking returns 201 with expected fields."""
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:00",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["message"] == "Appointment booked successfully."
        data = body["data"]
        assert "id" in data
        assert data["doctor_id"] == str(doctor.id)
        assert data["patient_id"] == str(patient.id)
        assert data["appointment_date"] == future_monday.isoformat()
        assert data["start_time"] == "10:00"
        assert data["status"] == "scheduled"


@pytest.mark.django_db
class TestBookingErrors:
    def test_booking_404_doctor_not_found(self, api_client, patient, working_hours):
        """Non-existent doctor_id returns 404."""
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(uuid.uuid4()),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:00",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_booking_404_patient_not_found(self, api_client, doctor, working_hours):
        """Non-existent patient_id returns 404."""
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(uuid.uuid4()),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:00",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_booking_409_slot_conflict(self, api_client, doctor, patient, working_hours):
        """Booking the same slot twice returns 409."""
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:00",
        }

        # First booking should succeed
        response1 = api_client.post("/appointments", payload, format="json")
        assert response1.status_code == 201

        # Second booking for same slot should conflict
        response2 = api_client.post("/appointments", payload, format="json")

        assert response2.status_code == 409
        data = response2.json()
        assert "detail" in data

    def test_booking_422_outside_working_hours(self, api_client, doctor, patient, working_hours):
        """Slot outside working hours returns 422.

        Working hours are 09:00–17:00; requesting 07:00 is outside.
        """
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "07:00",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_booking_422_past_slot(self, api_client, doctor, patient, working_hours):
        """Booking a slot in the past returns 422."""
        # Use a date clearly in the past
        past_date = date(2020, 1, 6)  # A Monday

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": past_date.isoformat(),
            "start_time": "10:00",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_booking_422_insufficient_lead_time(self, api_client, doctor, patient, working_hours):
        """Slot less than 1 hour from now returns 422.

        We mock datetime.utcnow() so that the slot is exactly 30 min in the future.
        """
        from datetime import datetime

        future_monday = _next_weekday_far_future()
        # Mock 'now' to be 09:30 on that Monday so that a 10:00 slot is only 30 min away
        fake_now = datetime(future_monday.year, future_monday.month, future_monday.day, 9, 30)

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:00",
        }

        with patch("appointments.services.booking.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fake_now
            mock_dt.combine = datetime.combine
            response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_booking_422_non_aligned_slot(self, api_client, doctor, patient, working_hours):
        """Non-30-minute-aligned slot returns 422."""
        future_monday = _next_weekday_far_future()

        payload = {
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "appointment_date": future_monday.isoformat(),
            "start_time": "10:15",
        }

        response = api_client.post("/appointments", payload, format="json")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
