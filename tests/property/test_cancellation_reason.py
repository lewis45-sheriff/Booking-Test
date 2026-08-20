# Feature: clinic-booking-system, Property 14: Cancellation reason length boundaries
"""
Property-based test for cancellation reason length validation.

Verifies that CancelSerializer accepts reasons of 1–500 characters
and rejects reasons of 0 chars or >500 chars.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from appointments.serializers import CancelSerializer


# ---------------------------------------------------------------------------
# Property 14: Cancellation reason length boundaries
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    length=st.integers(min_value=1, max_value=500),
)
def test_cancellation_reason_valid_length_accepted(length):
    """
    # Feature: clinic-booking-system, Property 14: Cancellation reason length boundaries

    **Validates: Requirements 3.1, 3.5**

    For any cancellation reason string of length 1 through 500 characters,
    the CancelSerializer SHALL accept it as valid.
    """
    reason = "a" * length
    serializer = CancelSerializer(data={"cancellation_reason": reason})
    assert serializer.is_valid(), (
        f"Expected valid for length {length}, got errors: {serializer.errors}"
    )


@settings(max_examples=100)
@given(
    length=st.integers(min_value=501, max_value=1000),
)
def test_cancellation_reason_too_long_rejected(length):
    """
    # Feature: clinic-booking-system, Property 14: Cancellation reason length boundaries

    **Validates: Requirements 3.1, 3.5**

    For any cancellation reason string of length > 500 characters,
    the CancelSerializer SHALL reject it as invalid.
    """
    reason = "a" * length
    serializer = CancelSerializer(data={"cancellation_reason": reason})
    assert not serializer.is_valid(), (
        f"Expected invalid for length {length}, but serializer was valid"
    )


def test_cancellation_reason_empty_string_rejected():
    """
    # Feature: clinic-booking-system, Property 14: Cancellation reason length boundaries

    **Validates: Requirements 3.1, 3.5**

    A cancellation reason of 0 characters (empty string) SHALL be rejected.
    """
    serializer = CancelSerializer(data={"cancellation_reason": ""})
    assert not serializer.is_valid()


def test_cancellation_reason_missing_field_rejected():
    """
    # Feature: clinic-booking-system, Property 14: Cancellation reason length boundaries

    **Validates: Requirements 3.1, 3.5**

    A missing cancellation_reason field SHALL be rejected.
    """
    serializer = CancelSerializer(data={})
    assert not serializer.is_valid()
