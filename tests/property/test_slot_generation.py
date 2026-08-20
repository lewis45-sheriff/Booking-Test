# Feature: clinic-booking-system, Property 1: Slot generation correctness
# Validates: Requirements 2.1, 2.4, 6.2, 6.5

from datetime import date, time

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from appointments.services.availability import WorkingHoursConfig, compute_slots


@settings(max_examples=200)
@given(
    start_hour=st.integers(min_value=6, max_value=20),
    start_minute=st.sampled_from([0, 30]),
    duration_slots=st.integers(min_value=1, max_value=16),
)
def test_slot_generation_correctness(start_hour, start_minute, duration_slots):
    """Property 1: Slot generation correctness.

    For any working hours configuration the generated slot list SHALL:
    - contain exactly floor((end_time - start_time) / 30 min) slots,
    - have every slot start time within [start_time, end_time),
    - have every slot end time (start + 30 min) <= end_time,
    - have all slot start minutes aligned to {0, 30}.
    """
    # Derive end_time from start_time + duration_slots * 30 minutes
    start_total_minutes = start_hour * 60 + start_minute
    end_total_minutes = start_total_minutes + duration_slots * 30

    # Skip cases where end_time would overflow past 23:30 (i.e. > 23*60+30 = 1410)
    assume(end_total_minutes <= 23 * 60 + 30)

    start_time = time(start_hour, start_minute)
    end_time = time(end_total_minutes // 60, end_total_minutes % 60)

    working_hours = WorkingHoursConfig(start_time=start_time, end_time=end_time)

    slots = compute_slots(working_hours, date.today())

    # 1. Exact slot count
    assert len(slots) == duration_slots, (
        f"Expected {duration_slots} slots for {start_time}–{end_time}, got {len(slots)}"
    )

    for slot in slots:
        slot_start_minutes = slot.hour * 60 + slot.minute
        slot_end_minutes = slot_start_minutes + 30

        # 2. Every slot start time is in [start_time, end_time)
        assert slot_start_minutes >= start_total_minutes, (
            f"Slot {slot} starts before working hours start {start_time}"
        )
        assert slot_start_minutes < end_total_minutes, (
            f"Slot {slot} starts at or after working hours end {end_time}"
        )

        # 3. Every slot end time (start + 30 min) is <= end_time
        assert slot_end_minutes <= end_total_minutes, (
            f"Slot ending at minute {slot_end_minutes} exceeds end_time {end_time} "
            f"({end_total_minutes} min)"
        )

        # 4. All slot start minutes are aligned to {0, 30}
        assert slot.minute in (0, 30), (
            f"Slot {slot} has minute={slot.minute}, expected 0 or 30"
        )
