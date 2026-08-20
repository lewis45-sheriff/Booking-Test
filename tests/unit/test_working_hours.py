# Feature: clinic-booking-system, Property 16: Working hours persistence round-trip
"""
Unit tests for WorkingHours model validation and persistence.

Covers:
- Property 15: Invalid working hours configuration rejected (start_time >= end_time)
- Property 16: Working hours persistence round-trip
"""
import pytest
from datetime import time

from hypothesis import given, settings
from hypothesis import strategies as st

from appointments.models import Doctor, WorkingHours


# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

def _make_time(hour: int, minute: int) -> time:
    """Return a time object, clamping hour to valid range."""
    return time(hour, minute)


# Generate (start_hour, start_minute) pairs where start is in range 0..22
# and minute is 0 or 30.
valid_start_st = st.builds(
    lambda h, m: (h, m),
    st.integers(min_value=0, max_value=22),
    st.sampled_from([0, 30]),
)


# ---------------------------------------------------------------------------
# Unit tests — invalid working hours (Property 15)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_working_hours_start_equals_end_rejected():
    """start_time == end_time should violate the DB CHECK constraint."""
    from django.db import IntegrityError, transaction

    doctor = Doctor.objects.create(name="Dr. Equal", specialty="General")
    with pytest.raises(Exception):  # IntegrityError or ValidationError
        with transaction.atomic():
            wh = WorkingHours(
                doctor=doctor,
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(9, 0),
            )
            wh.save()


@pytest.mark.django_db
def test_working_hours_start_after_end_rejected():
    """start_time > end_time should violate the DB CHECK constraint."""
    from django.db import IntegrityError, transaction

    doctor = Doctor.objects.create(name="Dr. Reversed", specialty="General")
    with pytest.raises(Exception):  # IntegrityError or ValidationError
        with transaction.atomic():
            wh = WorkingHours(
                doctor=doctor,
                day_of_week=0,
                start_time=time(10, 0),
                end_time=time(9, 0),
            )
            wh.save()


@pytest.mark.django_db
def test_working_hours_valid_range_accepted():
    """A valid start_time < end_time should be saved without error."""
    doctor = Doctor.objects.create(name="Dr. Valid", specialty="General")
    wh = WorkingHours.objects.create(
        doctor=doctor,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    assert wh.pk is not None


# ---------------------------------------------------------------------------
# Property 16: Working hours persistence round-trip
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@settings(max_examples=50)
@given(
    day_of_week=st.integers(min_value=0, max_value=6),
    start_hour=st.integers(min_value=0, max_value=22),
    start_minute=st.sampled_from([0, 30]),
    extra_slots=st.integers(min_value=1, max_value=16),  # at least 30 min gap
)
def test_working_hours_persistence_round_trip(
    day_of_week, start_hour, start_minute, extra_slots
):
    """
    # Feature: clinic-booking-system, Property 16: Working hours persistence round-trip

    **Validates: Requirements 6.1**

    For any valid working hours configuration (day_of_week, start_time, end_time),
    storing the configuration and then retrieving it by ID SHALL produce an equivalent
    configuration with the same day, start time, and end time.
    """
    # Compute end_time that is at least 30 min after start_time
    start_total_minutes = start_hour * 60 + start_minute
    end_total_minutes = start_total_minutes + extra_slots * 30

    # Skip if end_time would exceed 23:59
    if end_total_minutes >= 24 * 60:
        return

    end_hour = end_total_minutes // 60
    end_minute = end_total_minutes % 60

    start_time = _make_time(start_hour, start_minute)
    end_time = _make_time(end_hour, end_minute)

    # Create a fresh Doctor for each example to avoid unique_together conflicts
    doctor = Doctor.objects.create(name="Dr. RoundTrip", specialty="Test")

    # Persist WorkingHours
    wh = WorkingHours.objects.create(
        doctor=doctor,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    created_id = wh.id

    # Retrieve fresh from DB
    retrieved = WorkingHours.objects.get(id=created_id)

    # Assert round-trip correctness
    assert retrieved.day_of_week == day_of_week
    assert retrieved.start_time == start_time
    assert retrieved.end_time == end_time
