"""
Shared pytest-django fixtures and factory helpers for integration tests.
"""
import uuid
from datetime import date, time, timedelta

import pytest
from rest_framework.test import APIClient

from appointments.models import Appointment, Doctor, Patient, WorkingHours


# ---------------------------------------------------------------------------
# Fix: Monkey-patch Django's BaseHandler.make_view_atomic to handle missing
# ATOMIC_REQUESTS key gracefully. This is a known issue with certain
# combinations of Django + DRF + pytest-django.
# ---------------------------------------------------------------------------
from django.core.handlers.base import BaseHandler

_original_make_view_atomic = BaseHandler.make_view_atomic


def _patched_make_view_atomic(self, view, using=None):
    from django.db import connections
    # Django 5.1 signature: make_view_atomic(self, view)
    # Django 4.2 signature: make_view_atomic(self, view, using)
    # Patch all connections to ensure ATOMIC_REQUESTS exists
    for alias in connections:
        connections[alias].settings_dict.setdefault('ATOMIC_REQUESTS', False)
    if using is not None:
        return _original_make_view_atomic(self, view, using)
    else:
        return _original_make_view_atomic(self, view)


BaseHandler.make_view_atomic = _patched_make_view_atomic


# ---------------------------------------------------------------------------
# Basic fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    """DRF APIClient instance."""
    return APIClient()


@pytest.fixture
def doctor(db):
    """Create a test doctor."""
    return Doctor.objects.create(
        name="Dr. Test",
        specialty="General Practice",
    )


@pytest.fixture
def patient(db):
    """Create a test patient."""
    return Patient.objects.create(
        name="Test Patient",
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        phone="555-0100",
    )


@pytest.fixture
def working_hours(db, doctor):
    """Create working hours for the doctor (Monday–Friday, 09:00–17:00)."""
    hours = []
    for day in range(5):  # Monday through Friday
        wh = WorkingHours.objects.create(
            doctor=doctor,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        hours.append(wh)
    return hours


@pytest.fixture
def appointment(db, doctor, patient, working_hours):
    """Create a scheduled appointment for the next available weekday."""
    today = date.today()
    days_ahead = 1
    while (today + timedelta(days=days_ahead)).weekday() > 4:
        days_ahead += 1
    future_date = today + timedelta(days=days_ahead)

    return Appointment.objects.create(
        doctor=doctor,
        patient=patient,
        appointment_date=future_date,
        start_time=time(10, 0),
        status=Appointment.STATUS_SCHEDULED,
    )


# ---------------------------------------------------------------------------
# Factory fixtures — for flexible test data creation
# ---------------------------------------------------------------------------


@pytest.fixture
def create_doctor(db):
    """Factory fixture to create doctors with custom attributes."""

    def _create_doctor(**kwargs):
        defaults = {
            "name": f"Dr. {uuid.uuid4().hex[:6]}",
            "specialty": "General",
        }
        defaults.update(kwargs)
        return Doctor.objects.create(**defaults)

    return _create_doctor


@pytest.fixture
def create_patient(db):
    """Factory fixture to create patients with custom attributes."""

    def _create_patient(**kwargs):
        defaults = {
            "name": f"Patient {uuid.uuid4().hex[:6]}",
            "email": f"{uuid.uuid4().hex[:8]}@test.com",
            "phone": "555-0100",
        }
        defaults.update(kwargs)
        return Patient.objects.create(**defaults)

    return _create_patient


@pytest.fixture
def create_appointment(db):
    """Factory fixture to create appointments with custom attributes."""

    def _create_appointment(doctor, patient, **kwargs):
        defaults = {
            "appointment_date": date.today() + timedelta(days=7),
            "start_time": time(10, 0),
            "status": Appointment.STATUS_SCHEDULED,
        }
        defaults.update(kwargs)
        return Appointment.objects.create(doctor=doctor, patient=patient, **defaults)

    return _create_appointment
