"""
Unit tests for AvailabilityService — compute_slots and filter_available_slots.

Covers:
- Happy-path slot generation (09:00–12:00 → 6 slots)
- Empty working hours (None) → empty list
- Slot at exact boundary (09:00–09:30 → 1 slot at 09:00)
- Past date returns empty for filter_available_slots
"""
import pytest
from datetime import date, datetime, time

from appointments.services.availability import (
    WorkingHoursConfig,
    compute_slots,
    filter_available_slots,
)


# ---------------------------------------------------------------------------
# compute_slots tests
# ---------------------------------------------------------------------------


def test_compute_slots_happy_path_six_slots():
    """09:00–12:00 working hours should produce exactly 6 thirty-minute slots."""
    wh = WorkingHoursConfig(start_time=time(9, 0), end_time=time(12, 0))
    slots = compute_slots(wh, date(2020, 1, 1))

    assert len(slots) == 6
    assert slots[0] == time(9, 0)
    assert slots[1] == time(9, 30)
    assert slots[2] == time(10, 0)
    assert slots[3] == time(10, 30)
    assert slots[4] == time(11, 0)
    assert slots[5] == time(11, 30)


def test_compute_slots_none_working_hours_returns_empty():
    """Passing None as working_hours should return an empty list."""
    slots = compute_slots(None, date(2020, 1, 1))
    assert slots == []


def test_compute_slots_exact_boundary_one_slot():
    """Working hours 09:00–09:30 should produce exactly 1 slot at 09:00."""
    wh = WorkingHoursConfig(start_time=time(9, 0), end_time=time(9, 30))
    slots = compute_slots(wh, date(2020, 1, 1))

    assert len(slots) == 1
    assert slots[0] == time(9, 0)


# ---------------------------------------------------------------------------
# filter_available_slots tests
# ---------------------------------------------------------------------------


def test_filter_available_slots_past_date_returns_empty():
    """A query_date in the past relative to reference_time should return empty."""
    all_slots = [time(9, 0), time(9, 30), time(10, 0)]
    # reference_time is 2020-06-15, query_date is 2020-06-14 (yesterday)
    reference_time = datetime(2020, 6, 15, 8, 0, 0)
    query_date = date(2020, 6, 14)

    result = filter_available_slots(all_slots, [], reference_time, query_date)
    assert result == []
