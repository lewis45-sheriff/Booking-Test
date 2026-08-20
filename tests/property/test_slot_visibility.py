# Feature: clinic-booking-system, Property 3: Valid booking blocks slot
# Feature: clinic-booking-system, Property 4: Cancellation frees slot
# Feature: clinic-booking-system, Property 5: Reschedule frees original slot

from datetime import date, datetime, time

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from appointments.services.availability import (
    WorkingHoursConfig,
    compute_slots,
    filter_available_slots,
)

# ---------------------------------------------------------------------------
# Shared constants — reference_time well before all slots so lead-time doesn't
# interfere; query_date is a future date relative to reference_time.
# ---------------------------------------------------------------------------

REFERENCE_TIME = datetime(2020, 1, 1, 0, 0, 0)
QUERY_DATE = date(2025, 6, 15)


# ---------------------------------------------------------------------------
# Hypothesis strategy: generate valid working hours that produce at least
# `min_slots` 30-minute slots.
# ---------------------------------------------------------------------------

def working_hours_strategy(min_slots: int = 1):
    """Generate a WorkingHoursConfig with at least `min_slots` complete slots."""
    return st.builds(
        lambda start_hour, start_minute, duration_slots: WorkingHoursConfig(
            start_time=time(start_hour, start_minute),
            end_time=time(
                (start_hour * 60 + start_minute + duration_slots * 30) // 60,
                (start_hour * 60 + start_minute + duration_slots * 30) % 60,
            ),
        ),
        start_hour=st.integers(min_value=6, max_value=20),
        start_minute=st.sampled_from([0, 30]),
        duration_slots=st.integers(min_value=min_slots, max_value=16),
    ).filter(
        lambda wh: (wh.end_time.hour * 60 + wh.end_time.minute) <= 23 * 60 + 30
    )


# ---------------------------------------------------------------------------
# Property 3: Valid booking blocks slot
# Validates: Requirements 1.6, 9.4
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    working_hours=working_hours_strategy(min_slots=1),
    data=st.data(),
)
def test_property_3_valid_booking_blocks_slot(working_hours, data):
    """Property 3: Valid booking blocks slot.

    For any successfully created appointment for a given doctor, date, and
    start time, that start time SHALL NOT appear in the availability list
    returned for that same doctor and date.

    **Validates: Requirements 1.6, 9.4**
    """
    # Feature: clinic-booking-system, Property 3: Valid booking blocks slot
    all_slots = compute_slots(working_hours, QUERY_DATE)
    assume(len(all_slots) >= 1)

    # Pick a random valid slot from the computed slots
    slot_index = data.draw(st.integers(min_value=0, max_value=len(all_slots) - 1))
    booked_slot = all_slots[slot_index]

    # Simulate a booking by adding the slot to booked_slots
    booked_slots = [booked_slot]

    # Filter available slots
    available = filter_available_slots(all_slots, booked_slots, REFERENCE_TIME, QUERY_DATE)

    # The booked slot must NOT appear in the available list
    assert booked_slot not in available, (
        f"Booked slot {booked_slot} should not appear in available slots"
    )


# ---------------------------------------------------------------------------
# Property 4: Cancellation frees slot
# Validates: Requirements 3.2, 9.3
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    working_hours=working_hours_strategy(min_slots=1),
    data=st.data(),
)
def test_property_4_cancellation_frees_slot(working_hours, data):
    """Property 4: Cancellation frees slot.

    For any scheduled appointment that is subsequently cancelled, the
    associated start time SHALL reappear in the availability list returned
    for that doctor and date (assuming no other constraints apply).

    **Validates: Requirements 3.2, 9.3**
    """
    # Feature: clinic-booking-system, Property 4: Cancellation frees slot
    all_slots = compute_slots(working_hours, QUERY_DATE)
    assume(len(all_slots) >= 1)

    # Pick a random valid slot
    slot_index = data.draw(st.integers(min_value=0, max_value=len(all_slots) - 1))
    target_slot = all_slots[slot_index]

    # Use reference_time well before all slots so lead-time doesn't interfere
    reference_time = REFERENCE_TIME

    # Step 1: Simulate booking — slot is in booked_slots
    booked_slots = [target_slot]
    available_after_booking = filter_available_slots(
        all_slots, booked_slots, reference_time, QUERY_DATE
    )
    # Verify the slot is excluded while booked
    assert target_slot not in available_after_booking, (
        f"Slot {target_slot} should be excluded while booked"
    )

    # Step 2: Simulate cancellation — remove the slot from booked_slots
    booked_slots_after_cancel = []
    available_after_cancel = filter_available_slots(
        all_slots, booked_slots_after_cancel, reference_time, QUERY_DATE
    )

    # The slot must reappear in the available list
    assert target_slot in available_after_cancel, (
        f"Cancelled slot {target_slot} should reappear in available slots"
    )


# ---------------------------------------------------------------------------
# Property 5: Reschedule frees original slot
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    working_hours=working_hours_strategy(min_slots=2),
    data=st.data(),
)
def test_property_5_reschedule_frees_original_slot(working_hours, data):
    """Property 5: Reschedule frees original slot.

    For any scheduled appointment rescheduled to a different valid slot,
    the original start time SHALL reappear in the availability list for the
    original doctor and date, and the new start time SHALL NOT appear in the
    availability list for the new date.

    **Validates: Requirements 4.2**
    """
    # Feature: clinic-booking-system, Property 5: Reschedule frees original slot
    all_slots = compute_slots(working_hours, QUERY_DATE)
    assume(len(all_slots) >= 2)

    # Pick two distinct slots: slot_a (original) and slot_b (new)
    slot_a_index = data.draw(st.integers(min_value=0, max_value=len(all_slots) - 1))
    slot_b_index = data.draw(
        st.integers(min_value=0, max_value=len(all_slots) - 1).filter(
            lambda i: i != slot_a_index
        )
    )
    slot_a = all_slots[slot_a_index]
    slot_b = all_slots[slot_b_index]

    # Use reference_time well before all slots so lead-time doesn't interfere
    reference_time = REFERENCE_TIME

    # Step 1: Simulate initial booking of slot_a
    booked_slots = [slot_a]

    # Step 2: Simulate reschedule — remove slot_a, add slot_b
    booked_slots_after_reschedule = [slot_b]

    available_after_reschedule = filter_available_slots(
        all_slots, booked_slots_after_reschedule, reference_time, QUERY_DATE
    )

    # Original slot_a should reappear (it was freed by the reschedule)
    assert slot_a in available_after_reschedule, (
        f"Original slot {slot_a} should reappear after rescheduling away from it"
    )

    # New slot_b should NOT appear (it is now booked)
    assert slot_b not in available_after_reschedule, (
        f"New slot {slot_b} should not appear in available slots after rescheduling to it"
    )
