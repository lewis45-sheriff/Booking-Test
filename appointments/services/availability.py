"""Availability service — pure functions for slot computation."""
# Implemented in Tasks 4.1 and 4.3

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Optional


# ---------------------------------------------------------------------------
# WorkingHoursConfig — lightweight dataclass used by pure-function tests
# without requiring a DB-backed ORM model.  The Django WorkingHours model
# is duck-type compatible: both expose .start_time and .end_time attributes.
# ---------------------------------------------------------------------------

@dataclass
class WorkingHoursConfig:
    """Immutable value object representing a single day's working hours."""

    start_time: time
    end_time: time


# ---------------------------------------------------------------------------
# Slot interval constant
# ---------------------------------------------------------------------------

_SLOT_MINUTES = 30


def _time_to_minutes(t: time) -> int:
    """Convert a :class:`datetime.time` to total minutes since midnight."""
    return t.hour * 60 + t.minute


# ---------------------------------------------------------------------------
# Task 4.1 — compute_slots
# ---------------------------------------------------------------------------

def compute_slots(working_hours, date: date) -> list[time]:
    """Return a list of slot start times for *working_hours* on *date*.

    Each slot represents a complete 30-minute interval.  Only intervals that
    fit entirely within [start_time, end_time) are included.

    Parameters
    ----------
    working_hours:
        Any object with ``.start_time`` and ``.end_time`` :class:`~datetime.time`
        attributes (e.g. :class:`WorkingHoursConfig` or the ``WorkingHours``
        Django ORM model).  Pass ``None`` to receive an empty list.
    date:
        The calendar date for which slots are being computed.  Accepted by the
        function signature for future-extension/filtering purposes; it does not
        affect the slot list produced by the current implementation.

    Returns
    -------
    list[time]
        Slot start times in ascending order.  Returns an empty list when
        *working_hours* is ``None`` or ``start_time >= end_time``.
    """
    if working_hours is None:
        return []

    start_minutes = _time_to_minutes(working_hours.start_time)
    end_minutes = _time_to_minutes(working_hours.end_time)

    # Guard: degenerate or reversed interval
    if start_minutes >= end_minutes:
        return []

    slots: list[time] = []
    slot_start = start_minutes

    while slot_start + _SLOT_MINUTES <= end_minutes:
        slots.append(time(slot_start // 60, slot_start % 60))
        slot_start += _SLOT_MINUTES

    return slots


# ---------------------------------------------------------------------------
# Task 4.3 — filter_available_slots
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta


def filter_available_slots(
    all_slots: list[time],
    booked_slots: list[time],
    reference_time: datetime,
    query_date: date,
) -> list[time]:
    """Return the subset of *all_slots* that are available on *query_date*.

    Parameters
    ----------
    all_slots:
        All possible slot start times for the day (e.g. from ``compute_slots``).
    booked_slots:
        Slot start times that are already booked for this doctor/date.
    reference_time:
        The current wall-clock time (timezone-aware or naive, must be
        consistent with how caller obtains "now").
    query_date:
        The calendar date being queried.

    Returns
    -------
    list[time]
        Available slot start times in the same order as *all_slots*.
        Returns an empty list when *query_date* is in the past.

    Rules
    -----
    1. If ``query_date < reference_time.date()`` → return ``[]`` (past date).
    2. Skip any slot that appears in *booked_slots*.
    3. When ``query_date == reference_time.date()``, also skip any slot whose
       datetime is less than ``reference_time + 1 hour`` (lead-time guard).
    """
    # Rule 1: past date — return empty immediately
    if query_date < reference_time.date():
        return []

    booked_set: set[time] = set(booked_slots)
    is_today: bool = query_date == reference_time.date()
    cutoff: datetime = reference_time + timedelta(hours=1)

    result: list[time] = []
    for slot in all_slots:
        # Rule 2: skip booked slots
        if slot in booked_set:
            continue
        # Rule 3: skip slots too close to reference_time when querying today
        if is_today and datetime.combine(query_date, slot) < cutoff:
            continue
        result.append(slot)

    return result


# ---------------------------------------------------------------------------
# Task 8.4 — get_availability orchestration
# ---------------------------------------------------------------------------

def get_availability(doctor_id, query_date: date, now: datetime = None) -> list[time]:
    """Return available slot start times for a doctor on a given date.

    Parameters
    ----------
    doctor_id:
        UUID (or any PK type) identifying the doctor.
    query_date:
        The calendar date for which availability is requested.
    now:
        Reference datetime used as "current time".  Defaults to
        ``datetime.utcnow()`` when ``None``.

    Returns
    -------
    list[time]
        Available slot start times.  Returns an empty list when:
        - ``query_date`` is in the past,
        - the doctor has no working hours configured for that day of the week.

    Raises
    ------
    DoctorNotFoundError
        If no doctor with ``doctor_id`` exists.
    """
    # Step 1: default `now`
    if now is None:
        now = datetime.utcnow()

    # Step 2: reject past dates immediately (no DB access needed)
    if query_date < now.date():
        return []

    # Deferred imports to avoid circular dependency between services and repos
    from appointments.repositories.doctor_repo import DoctorRepo
    from appointments.repositories.appointment_repo import AppointmentRepo

    # Step 3: look up doctor — raises DoctorNotFoundError if missing
    DoctorRepo().get_by_id(doctor_id)

    # Step 4 & 5: determine day of week and retrieve working hours
    day_of_week = query_date.weekday()  # 0=Monday … 6=Sunday
    working_hours = DoctorRepo().get_working_hours(doctor_id, day_of_week)
    if working_hours is None:
        return []

    # Step 6: compute all theoretical slots for that day
    all_slots = compute_slots(working_hours, query_date)

    # Step 7: fetch booked slots from the DB
    booked_slots = AppointmentRepo().get_booked_slots(doctor_id, query_date)

    # Step 8: filter out past/near-future and booked slots
    return filter_available_slots(all_slots, booked_slots, now, query_date)
