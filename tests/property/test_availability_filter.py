# Feature: clinic-booking-system, Property 11: Availability excludes near-future slots when querying today
# Validates: Requirements 2.6

from datetime import date, datetime, time, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from appointments.services.availability import filter_available_slots


@settings(max_examples=200)
@given(offset_mins=st.integers(min_value=0, max_value=59))
def test_property_11_excludes_near_future_slots(offset_mins):
    # Feature: clinic-booking-system, Property 11: Availability excludes near-future slots when querying today
    reference_time = datetime(2025, 6, 15, 10, 0, 0)
    query_date = reference_time.date()
    slot_dt = reference_time + timedelta(minutes=offset_mins)
    assume(slot_dt > reference_time)
    slot_time = time(slot_dt.hour, slot_dt.minute)
    result = filter_available_slots([slot_time], [], reference_time, query_date)
    assert slot_time not in result


@settings(max_examples=200)
@given(offset_mins=st.integers(min_value=60, max_value=720))
def test_property_11_includes_far_future_slots(offset_mins):
    # Feature: clinic-booking-system, Property 11: Availability excludes near-future slots when querying today
    reference_time = datetime(2025, 6, 15, 10, 0, 0)
    query_date = reference_time.date()
    slot_dt = reference_time + timedelta(minutes=offset_mins)
    assume(slot_dt.date() == reference_time.date())
    slot_time = time(slot_dt.hour, slot_dt.minute)
    result = filter_available_slots([slot_time], [], reference_time, query_date)
    assert slot_time in result
