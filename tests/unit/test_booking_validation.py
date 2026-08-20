"""
Unit tests for BookingService validate_booking_request.

Covers:
- Valid slot accepted (no exception raised)
- Slot outside hours rejected (SlotOutsideWorkingHoursError)
- Non-aligned slot rejected (SlotNotAlignedError)
- Past slot rejected (SlotInPastError)
- Slot < 1 hr lead time rejected (InsufficientLeadTimeError)
- Exactly 1 hr lead time accepted (no exception)
"""
import pytest
from datetime import date, datetime, time

from appointments.exceptions import (
    InsufficientLeadTimeError,
    SlotInPastError,
    SlotNotAlignedError,
    SlotOutsideWorkingHoursError,
)
from appointments.services.availability import WorkingHoursConfig
from appointments.services.booking import validate_booking_request


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Working hours: 09:00–17:00 (standard day)
_WH = WorkingHoursConfig(start_time=time(9, 0), end_time=time(17, 0))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_slot_accepted():
    """A slot within hours, aligned, in the future with > 1 hr lead time passes."""
    # now is far in the past so slot is well in the future
    now = datetime(2020, 1, 1, 7, 0, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(10, 0)

    # Should not raise
    validate_booking_request(slot_time, slot_date, _WH, now)


def test_slot_outside_working_hours_rejected():
    """A slot before working hours start should raise SlotOutsideWorkingHoursError."""
    now = datetime(2020, 1, 1, 6, 0, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(8, 0)  # before 09:00 start

    with pytest.raises(SlotOutsideWorkingHoursError):
        validate_booking_request(slot_time, slot_date, _WH, now)


def test_non_aligned_slot_rejected():
    """A slot at :15 (not :00 or :30) should raise SlotNotAlignedError."""
    now = datetime(2020, 1, 1, 7, 0, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(10, 15)  # not aligned to 30-min boundary

    with pytest.raises(SlotNotAlignedError):
        validate_booking_request(slot_time, slot_date, _WH, now)


def test_past_slot_rejected():
    """A slot in the past should raise SlotInPastError."""
    now = datetime(2020, 1, 1, 12, 0, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(11, 0)  # before now (12:00)

    with pytest.raises(SlotInPastError):
        validate_booking_request(slot_time, slot_date, _WH, now)


def test_insufficient_lead_time_rejected():
    """A slot less than 1 hour from now should raise InsufficientLeadTimeError."""
    now = datetime(2020, 1, 1, 9, 30, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(10, 0)  # only 30 min from now

    with pytest.raises(InsufficientLeadTimeError):
        validate_booking_request(slot_time, slot_date, _WH, now)


def test_exactly_one_hour_lead_time_accepted():
    """A slot exactly 1 hour from now should be accepted (no exception)."""
    now = datetime(2020, 1, 1, 9, 0, 0)
    slot_date = date(2020, 1, 1)
    slot_time = time(10, 0)  # exactly 60 min from now

    # Should not raise
    validate_booking_request(slot_time, slot_date, _WH, now)
