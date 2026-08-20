"""
Integration tests for GET /doctors/{doctor_id}/availability?date=YYYY-MM-DD

Tests run against the actual Django stack using DRF's APIClient.
"""
import uuid
from datetime import date, timedelta

import pytest


def _next_weekday_far_future():
    """Return the next weekday (Mon-Fri) that is at least 8 days from today."""
    today = date.today()
    candidate = today + timedelta(days=8)
    while candidate.weekday() > 4:  # Skip Saturday (5) and Sunday (6)
        candidate += timedelta(days=1)
    return candidate


@pytest.mark.django_db
class TestAvailabilitySuccess:
    def test_availability_returns_slots(self, api_client, doctor, working_hours):
        """Doctor with 09:00–17:00 working hours, no bookings → 16 slots."""
        future_weekday = _next_weekday_far_future()

        response = api_client.get(
            f"/doctors/{doctor.id}/availability",
            {"date": future_weekday.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert "slots" in data
        assert len(data["slots"]) == 16  # (17:00 - 09:00) / 0:30 = 16 slots

    def test_availability_empty_no_working_hours(self, api_client, doctor):
        """Doctor with no working hours for requested day → empty list 200."""
        # doctor fixture exists but we don't use working_hours fixture,
        # so no WH records exist. Pick a weekday far in the future.
        future_weekday = _next_weekday_far_future()

        response = api_client.get(
            f"/doctors/{doctor.id}/availability",
            {"date": future_weekday.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["slots"] == []

    def test_availability_empty_past_date(self, api_client, doctor, working_hours):
        """Past date → empty list 200."""
        past_date = date(2020, 1, 6)  # A Monday in the past

        response = api_client.get(
            f"/doctors/{doctor.id}/availability",
            {"date": past_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["slots"] == []


@pytest.mark.django_db
class TestAvailabilityErrors:
    def test_availability_404_doctor_not_found(self, api_client):
        """Non-existent doctor UUID → 404."""
        future_weekday = _next_weekday_far_future()

        response = api_client.get(
            f"/doctors/{uuid.uuid4()}/availability",
            {"date": future_weekday.isoformat()},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_availability_422_malformed_date(self, api_client, doctor, working_hours):
        """Malformed date string → 422."""
        response = api_client.get(
            f"/doctors/{doctor.id}/availability",
            {"date": "not-a-date"},
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_availability_422_missing_date(self, api_client, doctor, working_hours):
        """No date query param → 422."""
        response = api_client.get(f"/doctors/{doctor.id}/availability")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
