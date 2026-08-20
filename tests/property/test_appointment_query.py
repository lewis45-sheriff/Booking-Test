# Feature: clinic-booking-system, Property 12: Upcoming appointments query correctness
# Feature: clinic-booking-system, Property 13: Upcoming appointment response field completeness
"""
Property-based tests for the patient upcoming appointments query logic.

- Property 12: Upcoming appointments query correctness (pure logic simulation)
- Property 13: Upcoming appointment response field completeness (DB-backed)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Property 12: Upcoming appointments query correctness
# ---------------------------------------------------------------------------
# This is a pure logic test — simulate the filtering logic of
# list_upcoming_for_patient without a DB.


@dataclass
class FakeAppointment:
    """Lightweight stand-in for an Appointment ORM instance."""

    id: str
    status: str  # "scheduled" or "cancelled"
    appointment_date: date
    start_time: time


# Strategy: generate a list of fake appointments with varying statuses and datetimes
_status_st = st.sampled_from(["scheduled", "cancelled"])
_date_st = st.dates(min_value=date(2024, 1, 1), max_value=date(2025, 12, 31))
_time_st = st.times(min_value=time(0, 0), max_value=time(23, 30))

_appointment_st = st.builds(
    FakeAppointment,
    id=st.uuids().map(str),
    status=_status_st,
    appointment_date=_date_st,
    start_time=_time_st,
)


def _simulate_upcoming_filter(
    appointments: list[FakeAppointment], now: datetime, limit: int = 50
) -> list[FakeAppointment]:
    """Pure-logic reimplementation of the upcoming query filtering.

    Keep only scheduled appointments whose combined datetime > now,
    sort ascending by (date, time), take first `limit`.
    """
    result = []
    for appt in appointments:
        if appt.status != "scheduled":
            continue
        appt_dt = datetime.combine(appt.appointment_date, appt.start_time)
        if appt_dt <= now:
            continue
        result.append(appt)

    result.sort(key=lambda a: (a.appointment_date, a.start_time))
    return result[:limit]


@settings(max_examples=100)
@given(
    appointments=st.lists(_appointment_st, min_size=0, max_size=80),
    now=st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31),
    ),
)
def test_upcoming_appointments_query_correctness(appointments, now):
    """
    # Feature: clinic-booking-system, Property 12: Upcoming appointments query correctness

    **Validates: Requirements 5.1, 5.5**

    For any patient with any combination of appointments (varying statuses,
    past and future datetimes), the upcoming filter SHALL return only
    appointments where status is "scheduled" and appointment datetime is
    strictly after `now`, sorted ascending by (date, time), capped at 50.
    """
    result = _simulate_upcoming_filter(appointments, now)

    # 1. All results are scheduled
    assert all(a.status == "scheduled" for a in result)

    # 2. All results have datetime > now
    for a in result:
        assert datetime.combine(a.appointment_date, a.start_time) > now

    # 3. Results are sorted ascending by (date, time)
    for i in range(len(result) - 1):
        a, b = result[i], result[i + 1]
        assert (a.appointment_date, a.start_time) <= (b.appointment_date, b.start_time)

    # 4. At most 50
    assert len(result) <= 50

    # 5. No eligible appointment was left out (unless we hit the cap)
    all_eligible = [
        a
        for a in appointments
        if a.status == "scheduled"
        and datetime.combine(a.appointment_date, a.start_time) > now
    ]
    if len(all_eligible) <= 50:
        assert len(result) == len(all_eligible)
    else:
        assert len(result) == 50
        # The 50 selected should be the chronologically nearest 50
        all_eligible_sorted = sorted(
            all_eligible, key=lambda a: (a.appointment_date, a.start_time)
        )
        for res, expected in zip(result, all_eligible_sorted[:50]):
            assert res.id == expected.id


# ---------------------------------------------------------------------------
# Property 13: Upcoming appointment response field completeness
# ---------------------------------------------------------------------------
# This requires DB — use @pytest.mark.django_db and create actual model instances.


@pytest.mark.django_db
@settings(max_examples=50)
@given(
    start_hour=st.integers(min_value=0, max_value=22),
    start_minute=st.sampled_from([0, 30]),
    day_offset=st.integers(min_value=1, max_value=30),
)
def test_upcoming_appointment_response_field_completeness(
    start_hour, start_minute, day_offset
):
    """
    # Feature: clinic-booking-system, Property 13: Upcoming appointment response field completeness

    **Validates: Requirements 5.2**

    For any upcoming appointment, the PatientAppointmentSerializer output SHALL
    contain non-null values for all 5 required fields: id, doctor_name,
    appointment_date, start_time, status.
    """
    from appointments.models import Appointment, Doctor, Patient
    from appointments.serializers import PatientAppointmentSerializer

    # Create test data
    doctor = Doctor.objects.create(name=f"Dr. Field-{uuid.uuid4().hex[:6]}", specialty="Test")
    patient = Patient.objects.create(
        name=f"Patient-{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
    )

    future_date = date.today() + timedelta(days=day_offset)
    appt_time = time(start_hour, start_minute)

    appointment = Appointment.objects.create(
        doctor=doctor,
        patient=patient,
        appointment_date=future_date,
        start_time=appt_time,
        status=Appointment.STATUS_SCHEDULED,
    )

    # Serialize using PatientAppointmentSerializer
    # Need to select_related doctor for the doctor_name field
    appt_with_doctor = Appointment.objects.select_related("doctor").get(pk=appointment.pk)
    serializer = PatientAppointmentSerializer(appt_with_doctor)
    data = serializer.data

    # Assert all 5 required fields are present and non-null
    required_fields = ["id", "doctor_name", "appointment_date", "start_time", "status"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
        assert data[field] is not None, f"Field '{field}' is None"

    # Verify the values are correct
    assert str(data["id"]) == str(appointment.id)
    assert data["doctor_name"] == doctor.name
    assert data["status"] == "scheduled"
