# Implementation Plan: Clinic Booking System

## Overview

Implement a Django + Django REST Framework REST API backed by PostgreSQL for scheduling 30-minute clinic appointments. The implementation follows a layered architecture: models → repositories → services (pure business logic) → serializers → views → URL routing. CI/CD is wired through GitHub Actions with a PostgreSQL service container.

## Tasks

- [x] 1. Set up Django project structure, configuration, and base dependencies
  - Create the `clinic_booking/` project layout with `config/` (settings, urls, wsgi) and `appointments/` app skeleton (models.py, serializers.py, views.py, urls.py, apps.py, admin.py, exceptions.py, services/, repositories/)
  - Add `requirements.txt` pinning Django, djangorestframework, psycopg2-binary, pytest-django, hypothesis, pytest-cov
  - Configure `config/settings.py`: INSTALLED_APPS, DATABASES (PostgreSQL via env vars), REST_FRAMEWORK with custom exception handler, DEFAULT_RENDERER_CLASSES
  - Create `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) with `DJANGO_SETTINGS_MODULE` and `python_files` glob
  - _Requirements: 9.1, 8.1_

- [x] 2. Implement Django ORM models and initial migration
  - [x] 2.1 Write `Doctor`, `Patient`, `WorkingHours`, and `Appointment` ORM models in `appointments/models.py`
    - `Doctor`: UUID PK, name, specialty, created_at
    - `Patient`: UUID PK, name, email (unique), phone, created_at
    - `WorkingHours`: UUID PK, doctor FK (CASCADE), day_of_week (0-6), start_time, end_time; unique_together (doctor, day_of_week)
    - `Appointment`: UUID PK, doctor FK (PROTECT), patient FK (PROTECT), appointment_date, start_time, status (scheduled/cancelled), cancellation_reason (nullable), created_at, updated_at (auto_now)
    - _Requirements: 6.1, 6.2_

  - [x] 2.2 Generate and apply the initial Django migration; add a `RunSQL` step for the partial unique index
    - `CREATE UNIQUE INDEX uq_appointment_slot_active ON appointments_appointment (doctor_id, appointment_date, start_time) WHERE status != 'cancelled'`
    - Add `CHECK (end_time > start_time)` constraint on WorkingHours via `AddConstraint`
    - _Requirements: 6.4, 1.3_

  - [x] 2.3 Write property test for working hours persistence round-trip (Property 16)
    - **Property 16: Working hours persistence round-trip**
    - **Validates: Requirements 6.1**
    - File: `tests/unit/test_working_hours.py`

- [x] 3. Implement the custom exception hierarchy and DRF exception handler
  - Write all domain exception classes in `appointments/exceptions.py` (`BookingSystemException` base plus all 404/409/422 subclasses)
  - Implement `booking_exception_handler` that maps domain exceptions to `{"detail": "…"}` responses and normalises DRF `ValidationError` to the same shape
  - Wire `EXCEPTION_HANDLER` in `config/settings.py`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 4. Implement the AvailabilityService (pure functions)
  - [x] 4.1 Write `compute_slots(working_hours, date) -> list[time]` in `appointments/services/availability.py`
    - Divide working hours into consecutive 30-min intervals; include only complete intervals
    - _Requirements: 2.1, 2.4, 6.2, 6.5_

  - [x] 4.2 Write property test for slot generation correctness (Property 1)
    - **Property 1: Slot generation correctness**
    - **Validates: Requirements 2.1, 2.4, 6.2, 6.5**
    - File: `tests/property/test_slot_generation.py`

  - [x] 4.3 Write `filter_available_slots(all_slots, booked_slots, reference_time, query_date) -> list[time]` in `appointments/services/availability.py`
    - Exclude booked slots; exclude slots < 60 min from `reference_time` when `query_date == reference_time.date()`
    - Return empty list when `query_date` is in the past
    - _Requirements: 2.2, 2.6, 2.7_

  - [x] 4.4 Write property test for availability filter near-future exclusion (Property 11)
    - **Property 11: Availability excludes near-future slots when querying today**
    - **Validates: Requirements 2.6**
    - File: `tests/property/test_availability_filter.py`

- [x] 5. Implement the BookingService validation (pure function)
  - [x] 5.1 Write `validate_booking_request(slot_time, slot_date, working_hours, now)` in `appointments/services/booking.py`
    - Raise `SlotOutsideWorkingHoursError` for out-of-hours slots
    - Raise `SlotNotAlignedError` for non-30-min-aligned slots
    - Raise `SlotInPastError` for past slot datetimes
    - Raise `InsufficientLeadTimeError` for slots within 60 min of now
    - _Requirements: 1.2, 1.4, 1.5, 1.9, 4.3, 4.5, 4.6_

  - [x] 5.2 Write property test for slot validation — out-of-working-hours rejection (Property 6)
    - **Property 6: Slot validation rejects out-of-working-hours slots**
    - **Validates: Requirements 1.2, 4.3**
    - File: `tests/property/test_booking_validation_props.py`

  - [x] 5.3 Write property test for slot validation — non-30-min-aligned rejection (Property 7)
    - **Property 7: Slot validation rejects non-30-min-aligned slots**
    - **Validates: Requirements 1.9**
    - File: `tests/property/test_booking_validation_props.py`

  - [x] 5.4 Write property test for slot validation — past slot rejection (Property 8)
    - **Property 8: Slot validation rejects past slots**
    - **Validates: Requirements 1.4, 4.5**
    - File: `tests/property/test_booking_validation_props.py`

  - [x] 5.5 Write property test for slot validation — 1-hour lead time enforcement (Property 9)
    - **Property 9: Slot validation enforces 1-hour lead time**
    - **Validates: Requirements 1.5, 4.6**
    - File: `tests/property/test_booking_validation_props.py`

- [x] 6. Checkpoint — Ensure all pure-function tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement data repositories
  - [x] 7.1 Write `AppointmentRepo` in `appointments/repositories/appointment_repo.py`
    - `get_by_id(appointment_id)` → raises `AppointmentNotFoundError` if missing
    - `get_booked_slots(doctor_id, date)` → list of start_time for non-cancelled appointments
    - `create(doctor_id, patient_id, date, start_time)` → Appointment ORM object; catches DB `IntegrityError` on unique index violation and re-raises as `SlotConflictError`
    - `cancel(appointment, reason)` → updates status and cancellation_reason
    - `reschedule(appointment, new_date, new_start_time)` → updates appointment_date and start_time; catches `IntegrityError` → `SlotConflictError`
    - `list_upcoming_for_patient(patient_id, now, limit=50)` → queryset filtered by status=scheduled, datetime > now, ordered by date+time, limited to 50
    - _Requirements: 1.1, 1.3, 1.6, 3.1, 3.2, 4.1, 4.2, 5.1, 5.5_

  - [x] 7.2 Write `DoctorRepo` in `appointments/repositories/doctor_repo.py`
    - `get_by_id(doctor_id)` → raises `DoctorNotFoundError` if missing
    - `get_working_hours(doctor_id, day_of_week)` → WorkingHours or None
    - _Requirements: 1.7, 2.3, 6.1, 6.3_

  - [x] 7.3 Write `PatientRepo` in `appointments/repositories/patient_repo.py`
    - `get_by_id(patient_id)` → raises `PatientNotFoundError` if missing
    - _Requirements: 1.8, 5.4_

- [x] 8. Implement higher-level service orchestration functions
  - [x] 8.1 Write `create_booking` orchestration in `appointments/services/booking.py`
    - Look up doctor (DoctorRepo) and patient (PatientRepo)
    - Look up working hours for the given day; raise `SlotOutsideWorkingHoursError` if none configured
    - Call `validate_booking_request`
    - Check for slot conflict via AppointmentRepo; raise `SlotConflictError` if booked
    - Persist via `AppointmentRepo.create`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 8.2 Write `cancel_appointment` orchestration in `appointments/services/cancellation.py`
    - Look up appointment; raise `AppointmentNotFoundError` if missing
    - Raise `AppointmentAlreadyCancelledError` if already cancelled
    - Persist cancellation via AppointmentRepo
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 8.3 Write `reschedule_appointment` orchestration in `appointments/services/reschedule.py`
    - Look up appointment; raise `AppointmentNotFoundError` if missing
    - Raise `CancelledAppointmentRescheduleError` if cancelled
    - Look up working hours for new slot day; validate with `validate_booking_request`
    - Check conflict for new slot; raise `SlotConflictError` if taken
    - Persist new slot, freeing original
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 8.4 Write `get_availability` orchestration in `appointments/services/availability.py`
    - Look up doctor; raise `DoctorNotFoundError` if missing
    - Retrieve working hours for the requested date's day_of_week; return empty list if none
    - Call `compute_slots` then `filter_available_slots` with booked slots from AppointmentRepo
    - Return empty list for past dates
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 6.3_

  - [x] 8.5 Write `list_upcoming_appointments` orchestration in `appointments/services/availability.py` (or a dedicated patient service)
    - Look up patient; raise `PatientNotFoundError` if missing
    - Delegate to `AppointmentRepo.list_upcoming_for_patient`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. Implement DRF serializers
  - Write `AppointmentCreateSerializer`, `AppointmentSerializer`, `CancelSerializer`, `RescheduleSerializer`, `AvailabilitySerializer`, and `PatientAppointmentSerializer` in `appointments/serializers.py`
  - `PatientAppointmentSerializer` must include appointment ID, doctor name, appointment date, start time, and status
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.2, 7.1_

- [x] 10. Implement DRF views and URL routing
  - [x] 10.1 Write `AppointmentBookView` (POST /appointments), `AppointmentCancelView` (PATCH /appointments/{id}/cancel), `AppointmentRescheduleView` (PATCH /appointments/{id}/reschedule), `DoctorAvailabilityView` (GET /doctors/{id}/availability), `PatientAppointmentsView` (GET /patients/{id}/appointments), and `HealthCheckView` (GET /health) in `appointments/views.py`
    - Each view delegates all business logic to the service layer and uses serializers for I/O
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 8.1_

  - [x] 10.2 Wire URL patterns in `appointments/urls.py` and include them in `config/urls.py`
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 8.1_

- [x] 11. Checkpoint — Ensure project runs locally and health endpoint responds
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Write unit tests for business logic
  - [x] 12.1 Write unit tests for `AvailabilityService` in `tests/unit/test_availability_service.py`
    - Happy-path slot generation, empty working hours, slot at exact boundary, past date returns empty
    - _Requirements: 2.1, 2.4, 6.2, 6.5_

  - [x] 12.2 Write unit tests for `BookingService` validation in `tests/unit/test_booking_validation.py`
    - Valid slot accepted, slot outside hours rejected, non-aligned slot rejected, past slot rejected, < 1 hr lead time rejected, exactly 1 hr lead time accepted
    - _Requirements: 1.2, 1.4, 1.5, 1.9_

  - [x] 12.3 Write unit tests for `WorkingHours` validation in `tests/unit/test_working_hours.py`
    - start_time == end_time rejected, start_time > end_time rejected, valid range accepted
    - _Requirements: 6.4_

- [x] 13. Write property-based tests for slot visibility (in-memory repository)
  - [x] 13.1 Write property test for valid booking blocks slot (Property 3)
    - **Property 3: Valid booking blocks slot**
    - **Validates: Requirements 1.6, 9.4**
    - File: `tests/property/test_slot_visibility.py`

  - [x] 13.2 Write property test for cancellation frees slot (Property 4)
    - **Property 4: Cancellation frees slot**
    - **Validates: Requirements 3.2, 9.3**
    - File: `tests/property/test_slot_visibility.py`

  - [x] 13.3 Write property test for reschedule frees original slot (Property 5)
    - **Property 5: Reschedule frees original slot**
    - **Validates: Requirements 4.2**
    - File: `tests/property/test_slot_visibility.py`

- [x] 14. Write property-based tests for appointment query correctness
  - [x] 14.1 Write property test for upcoming appointments query correctness (Property 12)
    - **Property 12: Upcoming appointments query correctness**
    - **Validates: Requirements 5.1, 5.5**
    - File: `tests/property/test_appointment_query.py`

  - [x] 14.2 Write property test for upcoming appointment response field completeness (Property 13)
    - **Property 13: Upcoming appointment response field completeness**
    - **Validates: Requirements 5.2**
    - File: `tests/property/test_appointment_query.py`

  - [x] 14.3 Write property test for cancellation reason length boundaries (Property 14)
    - **Property 14: Cancellation reason length boundaries**
    - **Validates: Requirements 3.1, 3.5**
    - File: `tests/property/test_cancellation_reason.py`

  - [x] 14.4 Write property test for invalid working hours configuration rejected (Property 15)
    - **Property 15: Invalid working hours configuration rejected**
    - **Validates: Requirements 6.4**
    - File: `tests/unit/test_working_hours.py`

- [x] 15. Write integration tests with pytest-django and APIClient
  - [x] 15.1 Write `tests/conftest.py` with pytest-django fixtures: `db`, `APIClient`, Doctor/Patient/WorkingHours/Appointment factories
    - _Requirements: 9.2_

  - [x] 15.2 Write integration tests for booking API in `tests/integration/test_booking_api.py`
    - Property 2 (booking response completeness), Property 3 (booking blocks slot), Property 10 (conflict detection prevents double-booking)
    - All 1.x error paths: 404 doctor, 404 patient, 409 conflict, 422 outside hours, 422 past, 422 < 1 hr, 422 non-aligned
    - **Validates: Requirements 1.1–1.9**

  - [x] 15.3 Write integration tests for availability API in `tests/integration/test_availability_api.py`
    - Property 1 (slot generation via HTTP), Property 11 (near-future exclusion via HTTP)
    - 404 doctor, 422 malformed date, empty list for no working hours, empty list for past date
    - **Validates: Requirements 2.1–2.7**

  - [x] 15.4 Write integration tests for cancellation API in `tests/integration/test_cancellation_api.py`
    - Property 4 (cancellation frees slot), Property 14 (reason length boundaries via HTTP)
    - 404 appointment, 409 already cancelled, 422 missing/empty/too-long reason
    - **Validates: Requirements 3.1–3.5**

  - [x] 15.5 Write integration tests for reschedule API in `tests/integration/test_reschedule_api.py`
    - Property 5 (reschedule frees original slot), Property 9 (lead time via HTTP)
    - 404 appointment, 409 new slot taken, 409 appointment already cancelled, 422 outside hours, 422 past, 422 < 1 hr
    - **Validates: Requirements 4.1–4.8**

  - [x] 15.6 Write integration tests for patient appointments API in `tests/integration/test_patient_appointments_api.py`
    - Property 12 (query correctness via HTTP), Property 13 (field completeness via HTTP)
    - 404 patient, empty list for no upcoming appointments, 50-appointment cap
    - **Validates: Requirements 5.1–5.5**

  - [x] 15.7 Write integration tests for health endpoint in `tests/integration/test_health.py`
    - GET /health returns 200 with `{"status": "ok"}`
    - **Validates: Requirements 8.1**

- [x] 16. Checkpoint — Ensure all tests pass and coverage ≥ 80% on `appointments/services/`
  - Run `pytest --cov=appointments/services --cov-fail-under=80`; ensure all tests pass, ask the user if questions arise.

- [x] 17. Set up CI/CD pipeline with GitHub Actions
  - [x] 17.1 Create `.github/workflows/ci.yml` with a `test` job
    - `ubuntu-latest` runner with a `postgres:15` service container (env vars for DB credentials, `pg_isready` health check)
    - Steps: `actions/checkout@v4`, `actions/setup-python@v5` (3.12), `pip install -r requirements.txt`, `python manage.py migrate`, `pytest --cov=appointments/services --cov-fail-under=80`
    - Triggered on `pull_request` and `push` to any branch
    - _Requirements: 8.2, 8.4, 9.2_

  - [x] 17.2 Create `.github/workflows/deploy.yml` with a `deploy` job
    - Triggered on `push` to `main` only; has `needs: test` dependency on the test job (or inline within the same workflow)
    - Deployment step targets Railway or Render via their respective GitHub Actions or CLI deploy commands
    - _Requirements: 8.3_

  - [x] 17.3 Create `Dockerfile` for containerised deployment
    - Python 3.12 slim base, copy requirements, `pip install`, copy source, expose port, `CMD ["gunicorn", "config.wsgi"]`
    - _Requirements: 8.1_

- [x] 18. Final checkpoint — Ensure all tests pass and CI pipeline is green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `max_examples=200` for core properties and `max_examples=100` for others
- Each property test must include a comment `# Feature: clinic-booking-system, Property N: <title>`
- The partial unique index on `appointments_appointment` is the DB-level safety net against race conditions; application-level checks come first to produce user-friendly errors
- Integration tests require a running PostgreSQL instance (provided by Docker in CI; configure `TEST` database in `settings.py` for local runs)
- Coverage is measured only on `appointments/services/` to target the business logic modules

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1"] },
    { "id": 1, "tasks": ["2.2", "3"] },
    { "id": 2, "tasks": ["2.3", "4.1", "5.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "5.2", "5.3", "5.4", "5.5", "7.1", "7.2", "7.3"] },
    { "id": 4, "tasks": ["4.4", "8.1", "8.2", "8.3", "8.4", "8.5"] },
    { "id": 5, "tasks": ["9", "10.1"] },
    { "id": 6, "tasks": ["10.2"] },
    { "id": 7, "tasks": ["12.1", "12.2", "12.3", "13.1", "13.2", "13.3", "14.1", "14.2", "14.3", "14.4"] },
    { "id": 8, "tasks": ["15.1"] },
    { "id": 9, "tasks": ["15.2", "15.3", "15.4", "15.5", "15.6", "15.7"] },
    { "id": 10, "tasks": ["17.1", "17.2", "17.3"] }
  ]
}
```
