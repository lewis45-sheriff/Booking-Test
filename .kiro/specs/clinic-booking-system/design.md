# Design Document: Clinic Booking System

## Overview

The Clinic Booking System is a REST API backend that allows patients to book, view, cancel, and reschedule 30-minute appointments with doctors at a small clinic (up to 5 doctors). It exposes a JSON API over HTTP/HTTPS, built with Python and Django + Django REST Framework (DRF), backed by a PostgreSQL database, and deployed via CI/CD to a cloud provider.

The system's core responsibility is scheduling: computing available slots from each doctor's configured working hours, enforcing booking rules (lead time, slot alignment, conflict detection), and maintaining consistent appointment state through a well-defined status lifecycle.

### Key Design Goals

- **Correctness first**: Slot availability is always derived from authoritative DB state, never cached inconsistently.
- **Clear separation of concerns**: Routing, business logic, data access, and models live in separate Python modules.
- **Consistent error contract**: All errors return JSON with a `detail` field and a semantically correct HTTP status code.
- **Testability**: Business logic is pure (no I/O side effects) so it can be property-tested without a database.

---

## Architecture

The system follows a layered architecture with four tiers:

```
┌──────────────────────────────────────────────────┐
│                   HTTP Clients                   │
└────────────────────┬─────────────────────────────┘
                     │ HTTP/JSON
┌────────────────────▼─────────────────────────────┐
│         Routing Layer (Django URLs + DRF)         │
│  /appointments  /doctors  /patients  /health      │
└────────────────────┬─────────────────────────────┘
                     │ Python function calls
┌────────────────────▼─────────────────────────────┐
│           Business Logic Layer (Services)         │
│  BookingService  AvailabilityService              │
│  CancellationService  RescheduleService           │
└────────────────────┬─────────────────────────────┘
                     │ Python function calls
┌────────────────────▼─────────────────────────────┐
│           Data Access Layer (Repositories)        │
│  AppointmentRepo  DoctorRepo  PatientRepo         │
└────────────────────┬─────────────────────────────┘
                     │ Django ORM / psycopg2
┌────────────────────▼─────────────────────────────┐
│                  PostgreSQL                       │
└──────────────────────────────────────────────────┘
```

### Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| Web framework | Django + Django REST Framework | Batteries-included, mature ecosystem, DRF provides serialization, viewsets, and exception handling |
| ORM | Django ORM (built-in) | Tightly integrated with Django models and migrations; no extra dependency needed |
| DB driver | psycopg2 (or psycopg3) | Standard, well-supported synchronous PostgreSQL driver for Django |
| Migrations | Django migrations (built-in) | First-class Django feature; no separate tool required |
| Validation | DRF Serializers | DRF serializers handle request parsing, field validation, and response serialization |
| Testing | pytest-django + Hypothesis | pytest-django integrates pytest with Django; Hypothesis for property-based tests |
| CI/CD | GitHub Actions | Standard, integrates with most cloud providers |
| Deployment | Railway / Render (cloud PaaS) | Simple Dockerfile-based deployment with managed Postgres |

### Concurrency and Slot Conflicts

Slot conflict detection must be race-condition-safe. The system uses a PostgreSQL unique constraint on `(doctor_id, appointment_date, start_time)` for non-cancelled appointments, enforced at the DB level via a partial unique index. Application-level conflict checks are done first for user-friendly error messages; the DB constraint is the final safety net.

---

## Components and Interfaces

### Module Structure

```
clinic_booking/           # Django project root
├── manage.py
├── config/
│   ├── settings.py       # Django settings (DB, installed apps, DRF config)
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py
├── appointments/         # Django app
│   ├── models.py         # Doctor, Patient, WorkingHours, Appointment ORM models
│   ├── serializers.py    # DRF serializers (request parsing + response shaping)
│   ├── views.py          # DRF APIView / ViewSet handlers
│   ├── urls.py           # App-level URL routing
│   ├── admin.py          # Django admin registrations (optional)
│   ├── apps.py           # AppConfig
│   ├── exceptions.py     # Custom exception classes → DRF error mapping
│   ├── services/
│   │   ├── __init__.py
│   │   ├── availability.py   # Slot computation logic (pure functions)
│   │   ├── booking.py        # Booking validation & creation logic
│   │   ├── cancellation.py   # Cancellation logic
│   │   └── reschedule.py     # Reschedule logic
│   └── repositories/
│       ├── __init__.py
│       ├── appointment_repo.py   # DB queries for appointments
│       ├── doctor_repo.py        # DB queries for doctors & working hours
│       └── patient_repo.py       # DB queries for patients
└── tests/
    ├── conftest.py           # pytest-django fixtures (db, client, factories)
    ├── unit/
    │   ├── test_availability_service.py
    │   ├── test_booking_validation.py
    │   └── test_working_hours.py
    ├── property/
    │   ├── test_slot_generation.py
    │   ├── test_booking_validation_props.py
    │   ├── test_availability_filter.py
    │   ├── test_slot_visibility.py
    │   ├── test_appointment_query.py
    │   └── test_cancellation_reason.py
    └── integration/
        ├── test_booking_api.py
        ├── test_availability_api.py
        ├── test_cancellation_api.py
        ├── test_reschedule_api.py
        ├── test_patient_appointments_api.py
        └── test_health.py
```

### REST API Endpoints

#### POST /appointments — Book an appointment
**Request body:**
```json
{
  "doctor_id": "uuid",
  "patient_id": "uuid",
  "appointment_date": "YYYY-MM-DD",
  "start_time": "HH:MM"
}
```
**Responses:**
- `201 Created` — appointment created, body contains `AppointmentResponse`
- `404` — doctor or patient not found
- `409` — slot already booked
- `422` — slot outside working hours, past slot, < 1 hour lead time, non-30-min-aligned

#### GET /doctors/{doctor_id}/availability?date=YYYY-MM-DD — View availability
**Responses:**
- `200 OK` — `{ "slots": ["HH:MM", ...] }` (may be empty)
- `404` — doctor not found
- `422` — missing or malformed date

#### PATCH /appointments/{appointment_id}/cancel — Cancel an appointment
**Request body:**
```json
{ "cancellation_reason": "string (1–500 chars)" }
```
**Responses:**
- `200 OK` — appointment marked cancelled
- `404` — appointment not found
- `409` — already cancelled
- `422` — reason missing, empty, or > 500 chars

#### PATCH /appointments/{appointment_id}/reschedule — Reschedule an appointment
**Request body:**
```json
{
  "appointment_date": "YYYY-MM-DD",
  "start_time": "HH:MM"
}
```
**Responses:**
- `200 OK` — appointment updated to new slot
- `404` — appointment not found
- `409` — new slot taken, or appointment already cancelled
- `422` — new slot outside working hours, in the past, < 1 hour lead time

#### GET /patients/{patient_id}/appointments — View upcoming appointments
**Responses:**
- `200 OK` — sorted list of up to 50 upcoming non-cancelled appointments
- `404` — patient not found

#### GET /health — Health check
**Responses:**
- `200 OK` — `{ "status": "ok" }`

### Service Interfaces

#### AvailabilityService
```python
def compute_slots(working_hours: WorkingHoursConfig, date: date) -> list[time]:
    """
    Pure function. Divides working hours into 30-min slots.
    Returns slot start times as time objects.
    Only complete 30-min intervals are included.
    """

def filter_available_slots(
    all_slots: list[time],
    booked_slots: list[time],
    reference_time: datetime,
    query_date: date,
) -> list[time]:
    """
    Pure function. Excludes booked slots and slots < 1 hour from reference_time
    when query_date == reference_time.date().
    """
```

#### BookingService
```python
def validate_booking_request(
    slot_time: time,
    slot_date: date,
    working_hours: WorkingHoursConfig,
    now: datetime,
) -> None:
    """
    Pure function. Raises domain exceptions on:
    - Slot outside working hours
    - Slot not aligned to 30-min boundary
    - Slot date/time in the past
    - Slot within 1 hour of now
    """
```

### DRF View Structure

Views are implemented as `APIView` subclasses (or `ViewSet` where appropriate). Each view delegates all business logic to the service layer and uses serializers for input validation and output serialization.

```python
# appointments/views.py (sketch)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class AppointmentBookView(APIView):
    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = booking_service.create_booking(**serializer.validated_data)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)

class AppointmentCancelView(APIView):
    def patch(self, request, appointment_id):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = cancellation_service.cancel(
            appointment_id, serializer.validated_data["cancellation_reason"]
        )
        return Response(AppointmentSerializer(appointment).data)
```

---

## Data Models

### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐
│   Doctor     │──1:N──│  WorkingHours    │
│──────────────│       │──────────────────│
│ id (PK)      │       │ id (PK)          │
│ name         │       │ doctor_id (FK)   │
│ specialty    │       │ day_of_week (0-6)│
│ created_at   │       │ start_time       │
└──────┬───────┘       │ end_time         │
       │               └──────────────────┘
       │ 1:N
       │
┌──────▼───────┐       ┌──────────────────┐
│ Appointment  │──N:1──│   Patient        │
│──────────────│       │──────────────────│
│ id (PK)      │       │ id (PK)          │
│ doctor_id(FK)│       │ name             │
│ patient_id(FK│       │ email            │
│ appt_date    │       │ phone            │
│ start_time   │       │ created_at       │
│ status       │       └──────────────────┘
│ cancel_reason│
│ created_at   │
│ updated_at   │
└──────────────┘
```

### PostgreSQL Schema

#### `appointments_doctor`
| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() |
| `name` | VARCHAR(255) | NOT NULL |
| `specialty` | VARCHAR(255) | |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |

#### `appointments_patient`
| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() |
| `name` | VARCHAR(255) | NOT NULL |
| `email` | VARCHAR(320) | NOT NULL, UNIQUE |
| `phone` | VARCHAR(50) | |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |

#### `appointments_workinghours`
| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() |
| `doctor_id` | UUID | NOT NULL, FK → appointments_doctor(id) ON DELETE CASCADE |
| `day_of_week` | SMALLINT | NOT NULL, CHECK (0–6), 0=Monday |
| `start_time` | TIME | NOT NULL |
| `end_time` | TIME | NOT NULL, CHECK (end_time > start_time) |
| | | UNIQUE (doctor_id, day_of_week) |

#### `appointments_appointment`
| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() |
| `doctor_id` | UUID | NOT NULL, FK → appointments_doctor(id) |
| `patient_id` | UUID | NOT NULL, FK → appointments_patient(id) |
| `appointment_date` | DATE | NOT NULL |
| `start_time` | TIME | NOT NULL |
| `status` | VARCHAR(20) | NOT NULL, CHECK IN ('scheduled', 'cancelled') |
| `cancellation_reason` | TEXT | nullable |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() |

> Table names follow Django's default `{app_label}_{model_name}` convention. The `appointments` app produces the prefix `appointments_`.

**Partial unique index** to enforce no double-booking of non-cancelled slots:
```sql
CREATE UNIQUE INDEX uq_appointment_slot_active
ON appointments_appointment (doctor_id, appointment_date, start_time)
WHERE status != 'cancelled';
```

This index is created via a Django migration using `AddConstraint` with a `UniqueConstraint(..., condition=~Q(status='cancelled'))` or a raw `RunSQL` migration step.

### Django ORM Models

```python
# appointments/models.py
import uuid
from django.db import models

class Doctor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=320, unique=True)
    phone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WorkingHours(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.SmallIntegerField()  # 0=Monday … 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = [('doctor', 'day_of_week')]

class Appointment(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [(STATUS_SCHEDULED, 'Scheduled'), (STATUS_CANCELLED, 'Cancelled')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='appointments')
    appointment_date = models.DateField()
    start_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    cancellation_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # The partial unique index is added via a RunSQL migration
        constraints = []
```

### Appointment Status Lifecycle

```
[POST /appointments]
        │
        ▼
   ┌─────────┐
   │scheduled│ ──── PATCH /cancel ───► [cancelled]
   └─────────┘ ──── PATCH /reschedule ─► [scheduled] (new slot, old slot freed)
```

### DRF Serializers

DRF serializers replace Pydantic schemas for request parsing/validation and response serialization.

```python
# appointments/serializers.py
from rest_framework import serializers
from .models import Appointment

class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField(format='%H:%M', input_formats=['%H:%M'])

class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['id', 'doctor_id', 'patient_id', 'appointment_date', 'start_time', 'status']

class CancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(min_length=1, max_length=500)

class RescheduleSerializer(serializers.Serializer):
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField(format='%H:%M', input_formats=['%H:%M'])

class AvailabilitySerializer(serializers.Serializer):
    slots = serializers.ListField(child=serializers.TimeField(format='%H:%M'))
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

The pure service functions (`compute_slots`, `filter_available_slots`, `validate_booking_request`) are the primary targets for property-based testing. They take well-defined inputs and return deterministic outputs with no I/O side effects, making them ideal candidates. Higher-level integration behavior (slot visibility after create/cancel/reschedule) is tested with a lightweight in-memory repository for fast iteration.

---

### Property 1: Slot generation correctness

*For any* doctor's working hours configuration (start time, end time) on a given date, the generated slot list SHALL contain exactly `floor((end_time - start_time) / 30 minutes)` slots, every slot start time SHALL fall within `[start_time, end_time)`, every slot end time (`start_time + 30 min`) SHALL be ≤ `end_time`, and all slot start times SHALL be aligned to a 30-minute boundary (i.e., minute ∈ {0, 30}).

**Validates: Requirements 2.1, 2.4, 6.2, 6.5**

---

### Property 2: Booking response completeness

*For any* valid booking request (existing doctor, existing patient, future slot ≥ 1 hour from now, slot within working hours, slot 30-min aligned, no existing appointment for that slot), the created Appointment SHALL contain a non-null appointment ID, the exact doctor ID, patient ID, appointment date, start time, and status equal to `"scheduled"`.

**Validates: Requirements 1.1**

---

### Property 3: Valid booking blocks slot

*For any* successfully created appointment for a given doctor, date, and start time, that start time SHALL NOT appear in the availability list returned for that same doctor and date.

**Validates: Requirements 1.6, 9.4**

---

### Property 4: Cancellation frees slot

*For any* scheduled appointment that is subsequently cancelled with a valid reason, the associated start time SHALL reappear in the availability list returned for that doctor and date (assuming no other constraints such as the 1-hour lead time filter apply).

**Validates: Requirements 3.2, 9.3**

---

### Property 5: Reschedule frees original slot

*For any* scheduled appointment rescheduled to a different valid slot, the original start time SHALL reappear in the availability list for the original doctor and date, and the new start time SHALL NOT appear in the availability list for the new date.

**Validates: Requirements 4.2**

---

### Property 6: Slot validation rejects out-of-working-hours slots

*For any* working hours configuration and any slot time that does not fall within the working hours interval, calling `validate_booking_request` SHALL raise a domain exception indicating the slot is outside working hours.

**Validates: Requirements 1.2, 4.3**

---

### Property 7: Slot validation rejects non-30-min-aligned slots

*For any* slot time whose minute component is not in `{0, 30}`, calling `validate_booking_request` SHALL raise a domain exception indicating the slot is not aligned to a 30-minute boundary.

**Validates: Requirements 1.9**

---

### Property 8: Slot validation rejects past slots

*For any* slot datetime that is strictly before the current reference time, calling `validate_booking_request` SHALL raise a domain exception indicating past slots cannot be booked.

**Validates: Requirements 1.4, 4.5**

---

### Property 9: Slot validation enforces 1-hour lead time

*For any* slot datetime that is in the future but within 60 minutes of the current reference time (i.e., `now < slot_datetime < now + 60 min`), calling `validate_booking_request` SHALL raise a domain exception indicating insufficient lead time.

**Validates: Requirements 1.5, 4.6**

---

### Property 10: Conflict detection prevents double-booking

*For any* appointment that exists with a given doctor, date, and start time in `"scheduled"` status, attempting to create a second appointment for the same doctor, date, and start time SHALL raise a conflict exception.

**Validates: Requirements 1.3, 4.4**

---

### Property 11: Availability excludes near-future slots when querying today

*For any* set of available slots on today's date and any reference time, `filter_available_slots` SHALL exclude all slots whose start datetime is less than 60 minutes from the reference time, and SHALL include all slots whose start datetime is ≥ 60 minutes from the reference time (subject to no other exclusions).

**Validates: Requirements 2.6**

---

### Property 12: Upcoming appointments query correctness

*For any* patient with any combination of appointments (varying statuses, past and future datetimes), `list_upcoming_appointments` SHALL return only appointments where status is `"scheduled"` and appointment datetime is strictly after the current server time, sorted in ascending date+time order, and the result set SHALL contain at most 50 appointments (specifically the chronologically nearest 50 if more exist).

**Validates: Requirements 5.1, 5.5**

---

### Property 13: Upcoming appointment response field completeness

*For any* upcoming appointment returned in the list, the response object SHALL contain non-null values for all five required fields: appointment ID, doctor name, appointment date, start time, and appointment status.

**Validates: Requirements 5.2**

---

### Property 14: Cancellation reason length boundaries

*For any* cancellation reason string of length 1 through 500 characters, the cancellation SHALL be accepted. *For any* cancellation reason string of length 0 or length > 500 characters, the cancellation SHALL be rejected with a validation error.

**Validates: Requirements 3.1, 3.5**

---

### Property 15: Invalid working hours configuration rejected

*For any* working hours configuration where `start_time >= end_time`, the system SHALL reject the configuration with HTTP status 422.

**Validates: Requirements 6.4**

---

### Property 16: Working hours persistence round-trip

*For any* valid working hours configuration (day_of_week, start_time, end_time), storing the configuration and then retrieving it SHALL produce an equivalent configuration with the same day, start time, and end time.

**Validates: Requirements 6.1**

---

## Error Handling

### Exception Hierarchy

All domain errors extend a base `BookingSystemException`. A DRF custom exception handler maps each subclass to the appropriate HTTP status code and a JSON body containing `{"detail": "<message>"}`.

```python
# appointments/exceptions.py

class BookingSystemException(Exception):
    http_status: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


# 404 Not Found
class DoctorNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Doctor not found."

class PatientNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Patient not found."

class AppointmentNotFoundError(BookingSystemException):
    http_status = 404
    default_message = "Appointment not found."


# 409 Conflict
class SlotConflictError(BookingSystemException):
    http_status = 409
    default_message = "The requested slot is already booked."

class AppointmentAlreadyCancelledError(BookingSystemException):
    http_status = 409
    default_message = "The appointment is already cancelled."

class CancelledAppointmentRescheduleError(BookingSystemException):
    http_status = 409
    default_message = "Cancelled appointments cannot be rescheduled."


# 422 Unprocessable Entity
class SlotOutsideWorkingHoursError(BookingSystemException):
    http_status = 422
    default_message = "The slot falls outside the doctor's working hours."

class SlotNotAlignedError(BookingSystemException):
    http_status = 422
    default_message = "The slot must align to a 30-minute boundary (:00 or :30)."

class SlotInPastError(BookingSystemException):
    http_status = 422
    default_message = "Past slots cannot be booked."

class InsufficientLeadTimeError(BookingSystemException):
    http_status = 422
    default_message = "Booking requires at least 1 hour of lead time."

class InvalidCancellationReasonError(BookingSystemException):
    http_status = 422
    default_message = "Cancellation reason must be between 1 and 500 characters."

class InvalidWorkingHoursError(BookingSystemException):
    http_status = 422
    default_message = "Working hours start time must be before end time."
```

### DRF Custom Exception Handler

DRF's exception handling is customised via `EXCEPTION_HANDLER` in `settings.py`. The custom handler intercepts domain exceptions and DRF's own `ValidationError` (raised by `serializer.is_valid(raise_exception=True)`) to normalise all error responses to the `{"detail": "<string>"}` contract.

```python
# appointments/exceptions.py  (handler function)
from rest_framework.views import exception_handler
from rest_framework.response import Response

def booking_exception_handler(exc, context):
    # Handle our domain exceptions first
    if isinstance(exc, BookingSystemException):
        return Response({"detail": exc.message}, status=exc.http_status)

    # Fall back to DRF's default handler for ValidationError, NotFound, etc.
    response = exception_handler(exc, context)
    if response is not None:
        # Normalise DRF validation errors (list format) to a single string
        detail = response.data.get("detail", response.data)
        if isinstance(detail, list):
            detail = " ".join(str(d) for d in detail)
        elif isinstance(detail, dict):
            detail = "; ".join(f"{k}: {v}" for k, v in detail.items())
        response.data = {"detail": str(detail)}
    return response
```

```python
# config/settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "appointments.exceptions.booking_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
```

### Error Response Guarantee

Every error response from the API (4xx, 5xx) SHALL contain a JSON body with at minimum a `"detail"` field of type `string`. This is enforced by:
1. Domain exceptions mapped via `booking_exception_handler`
2. DRF serializer `ValidationError` normalised by the same handler
3. Django's `500` handler overridden to return `{"detail": "Internal server error"}`

---

## Testing Strategy

### Dual Testing Approach

The testing strategy combines **unit/property-based tests** for pure business logic with **integration tests** for the full API stack.

```
tests/
├── conftest.py                          # pytest-django fixtures, DB setup, factories
├── unit/
│   ├── test_availability_service.py     # Properties 1, 11
│   ├── test_booking_validation.py       # Properties 6, 7, 8, 9
│   └── test_working_hours.py            # Properties 15, 16
├── property/
│   ├── test_slot_generation.py          # Property 1
│   ├── test_booking_validation_props.py # Properties 6, 7, 8, 9
│   ├── test_availability_filter.py      # Property 11
│   ├── test_slot_visibility.py          # Properties 3, 4, 5 (in-memory repo)
│   ├── test_appointment_query.py        # Properties 12, 13
│   └── test_cancellation_reason.py      # Property 14
└── integration/
    ├── test_booking_api.py              # Properties 2, 3, 10 (full HTTP via DRF test client)
    ├── test_availability_api.py         # Properties 1, 11 (full HTTP)
    ├── test_cancellation_api.py         # Properties 4, 14 (full HTTP)
    ├── test_reschedule_api.py           # Properties 5, 9 (full HTTP)
    ├── test_patient_appointments_api.py # Properties 12, 13 (full HTTP)
    └── test_health.py                   # Smoke test (Requirement 8.1)
```

### Property-Based Testing with Hypothesis

The project uses [**Hypothesis**](https://hypothesis.readthedocs.io/) as the property-based testing library, integrated with pytest via **pytest-django**.

```python
# tests/property/test_slot_generation.py
# Feature: clinic-booking-system, Property 1: Slot generation correctness

from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import time, timedelta, date, datetime
from appointments.services.availability import compute_slots

@settings(max_examples=200)
@given(
    start_hour=st.integers(min_value=6, max_value=20),
    start_minute=st.sampled_from([0, 30]),
    duration_slots=st.integers(min_value=1, max_value=16),  # up to 8 hours
)
def test_slot_generation_correctness(start_hour, start_minute, duration_slots):
    # Feature: clinic-booking-system, Property 1: Slot generation correctness
    start = time(start_hour, start_minute)
    end_minutes = (start_hour * 60 + start_minute) + duration_slots * 30
    end = time(end_minutes // 60, end_minutes % 60)
    working_hours = WorkingHoursConfig(start_time=start, end_time=end)

    slots = compute_slots(working_hours, date.today())

    assert len(slots) == duration_slots
    for slot in slots:
        assert slot.minute in (0, 30)
        assert start <= slot < end
        slot_end = (datetime.combine(date.today(), slot) + timedelta(minutes=30)).time()
        assert slot_end <= end
```

**Integration tests use DRF's `APIClient`** (instead of `httpx.AsyncClient`), paired with `pytest-django`'s `@pytest.mark.django_db` marker and `db` fixture:

```python
# tests/integration/test_booking_api.py
import pytest
from rest_framework.test import APIClient
from django.urls import reverse

@pytest.fixture
def client():
    return APIClient()

@pytest.mark.django_db
def test_book_appointment_returns_201(client, doctor, patient):
    # Feature: clinic-booking-system, Property 2: Booking response completeness
    url = reverse('appointment-book')
    payload = {
        "doctor_id": str(doctor.id),
        "patient_id": str(patient.id),
        "appointment_date": "2025-12-01",
        "start_time": "09:00",
    }
    response = client.post(url, payload, format='json')
    assert response.status_code == 201
    data = response.json()
    assert all(k in data for k in ['id', 'doctor_id', 'patient_id', 'appointment_date', 'start_time', 'status'])
    assert data['status'] == 'scheduled'
```

**pytest-django configuration** (`pytest.ini` or `pyproject.toml`):
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests/**/test_*.py
```

**Test configuration:**
- Minimum **100 iterations** per property test (`max_examples=100`; set to 200 for core properties)
- Each property test is tagged with a comment: `# Feature: clinic-booking-system, Property N: <property text>`
- Each correctness property from the design document maps to exactly one property test function
- Integration tests use `@pytest.mark.django_db` and run against a real test PostgreSQL database (via Docker in CI)
- Django's test runner creates and tears down the test database automatically per session

### Unit Test Focus Areas

Unit tests cover:
- Specific valid booking examples (happy path)
- Specific error examples (non-existent doctor/patient ID, malformed dates)
- Edge cases: empty working hours, slot exactly at boundary, exactly 1 hour lead time

### Integration Test Focus Areas

Integration tests use `pytest-django` + `rest_framework.test.APIClient` + a test PostgreSQL database (via Docker in CI):
- Full HTTP request/response cycle through Django's URL dispatcher → DRF views → services → Django ORM → PostgreSQL
- DB persistence and the partial unique index constraint (race condition safety)
- Health check endpoint
- Error response structure (`detail` field present on all errors)

### Coverage Requirements

- Business logic modules (`appointments/services/`) must achieve ≥ 80% line coverage
- Measured with `pytest-cov`
- CI enforces coverage gate: build fails if coverage drops below 80%

### CI/CD Testing Pipeline

```yaml
# .github/workflows/ci.yml (conceptual)
on: [pull_request, push to main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: clinic_test
          POSTGRES_USER: clinic
          POSTGRES_PASSWORD: clinic
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python manage.py migrate --settings=config.settings_test
      - run: pytest --cov=appointments/services --cov-fail-under=80

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - Deploy to cloud provider (Railway / Render)
```
