"""Property-based tests for validate_booking_request."""
# Feature: clinic-booking-system, Properties 6-9: Slot validation

from datetime import date, datetime, time, timedelta

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from appointments.exceptions import (
    InsufficientLeadTimeError,
    SlotInPastError,
    SlotNotAlignedError,
    SlotOutsideWorkingHoursError,
)
from appointments.services.availability import WorkingHoursConfig
from appointments.services.booking import validate_booking_request


# ---------------------------------------------------------------------------
# Property 6: Slot validation rejects out-of-working-hours slots
# Validates: Requirements 1.2, 4.3
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    start_hour=st.integers(min_value=6, max_value=15),
    duration_slots=st.integers(min_value=1, max_value=8),
    slot_offset_before=st.integers(min_value=30, max_value=300),  # minutes before start
    use_before=st.booleans(),
)
def test_property_6_rejects_out_of_working_hours(
    start_hour, duration_slots, slot_offset_before, use_before
):
    # Feature: clinic-booking-system, Property 6: Slot validation rejects out-of-working-hours slots
    start_minutes = start_hour * 60
    end_minutes = start_minutes + duration_slots * 30

    assume(end_minutes <= 23 * 60)  # keep end time sane

    start_time = time(start_minutes // 60, start_minutes % 60)
    end_time = time(end_minutes // 60, end_minutes % 60)
    working_hours = WorkingHoursConfig(start_time=start_time, end_time=end_time)

    # Use a `now` well in the past so past/lead-time checks don't interfere
    now = datetime(2020, 1, 1, 0, 0, 0)
    slot_date = date(2020, 1, 2)  # always in the future relative to `now`

    if use_before:
        # Slot is strictly before start_time
        slot_minutes = start_minutes - slot_offset_before
        assume(slot_minutes >= 0)
        slot_time = time(slot_minutes // 60, slot_minutes % 60)
    else:
        # Slot is at or after end_time (on a 30-min boundary at/after end)
        slot_minutes = end_minutes
        assume(slot_minutes < 24 * 60)
        slot_time = time(slot_minutes // 60, slot_minutes % 60)

    with pytest.raises(SlotOutsideWorkingHoursError):
        validate_booking_request(slot_time, slot_date, working_hours, now)


# ---------------------------------------------------------------------------
# Property 7: Slot validation rejects non-30-min-aligned slots
# Validates: Requirements 1.9
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    hour=st.integers(min_value=1, max_value=22),
    minute=st.integers(min_value=1, max_value=59),
)
def test_property_7_rejects_non_aligned_slots(hour, minute):
    # Feature: clinic-booking-system, Property 7: Slot validation rejects non-30-min-aligned slots
    assume(minute not in (0, 30))

    slot_time = time(hour, minute)

    # Wide working hours containing the slot (00:00 to 23:00) so working-hours check passes
    working_hours = WorkingHoursConfig(
        start_time=time(0, 0),
        end_time=time(23, 0),
    )

    # `now` in the past so past/lead-time checks don't interfere
    now = datetime(2020, 1, 1, 0, 0, 0)
    slot_date = date(2020, 1, 2)

    with pytest.raises(SlotNotAlignedError):
        validate_booking_request(slot_time, slot_date, working_hours, now)


# ---------------------------------------------------------------------------
# Property 8: Slot validation rejects past slots
# Validates: Requirements 1.4, 4.5
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    offset_minutes=st.integers(min_value=1, max_value=60 * 24 * 365),  # 1 min to 1 year in the past
)
def test_property_8_rejects_past_slots(offset_minutes):
    # Feature: clinic-booking-system, Property 8: Slot validation rejects past slots
    now = datetime(2025, 6, 15, 12, 0, 0)
    slot_dt = now - timedelta(minutes=offset_minutes)

    slot_date = slot_dt.date()
    slot_time = slot_dt.time().replace(second=0, microsecond=0)

    # Wide working hours so hours check doesn't interfere
    working_hours = WorkingHoursConfig(
        start_time=time(0, 0),
        end_time=time(23, 30),
    )

    with pytest.raises(SlotInPastError):
        validate_booking_request(slot_time, slot_date, working_hours, now)


# ---------------------------------------------------------------------------
# Property 9: Slot validation enforces 1-hour lead time
# Validates: Requirements 1.5, 4.6
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    lead_minutes=st.integers(min_value=1, max_value=59),
    aligned_to_30=st.booleans(),
)
def test_property_9_enforces_lead_time(lead_minutes, aligned_to_30):
    # Feature: clinic-booking-system, Property 9: Slot validation enforces 1-hour lead time
    # Use a fixed `now` at a clean boundary
    now = datetime(2025, 6, 15, 10, 0, 0)

    # Build a slot_dt that is `lead_minutes` into the future, then snap to nearest :00 or :30
    raw_dt = now + timedelta(minutes=lead_minutes)

    # Snap to :00 or :30 (round up to next boundary so slot is strictly after now)
    if aligned_to_30:
        snapped_minute = 30 if raw_dt.minute < 30 else 0
        if raw_dt.minute >= 30:
            # rolled over to next hour
            raw_dt = raw_dt.replace(minute=0) + timedelta(hours=1)
        else:
            raw_dt = raw_dt.replace(minute=30, second=0, microsecond=0)
    else:
        snapped_minute = 0
        raw_dt = raw_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    slot_dt = raw_dt.replace(second=0, microsecond=0)

    # The snapped slot must still be strictly after now and strictly less than now + 60 min
    assume(now < slot_dt < now + timedelta(hours=1))

    slot_date = slot_dt.date()
    slot_time = slot_dt.time()

    # Confirm alignment
    assume(slot_time.minute in (0, 30))

    # Wide working hours that contain the slot
    working_hours = WorkingHoursConfig(
        start_time=time(0, 0),
        end_time=time(23, 30),
    )

    with pytest.raises(InsufficientLeadTimeError):
        validate_booking_request(slot_time, slot_date, working_hours, now)
