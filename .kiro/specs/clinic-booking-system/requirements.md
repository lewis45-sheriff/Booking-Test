# Requirements Document

## Introduction

This document defines the requirements for an online clinic booking system serving a small clinic with 5 doctors. The system enables patients to view available appointment slots, book appointments, cancel bookings, and reschedule existing appointments. Each doctor operates in 30-minute time slots within defined working hours. The system is built with Python/FastAPI, backed by PostgreSQL, and deployed via CI/CD to a cloud provider.

## Glossary

- **Booking_System**: The backend API application that manages appointment scheduling for the clinic.
- **Doctor**: A medical professional registered in the system with defined working hours and 30-minute appointment slots.
- **Patient**: A person who uses the system to book, cancel, or reschedule appointments with doctors.
- **Slot**: A 30-minute time window within a doctor's working hours that can hold one appointment.
- **Appointment**: A confirmed booking linking a patient to a specific doctor at a specific slot.
- **Working_Hours**: The defined start and end times during which a doctor is available for appointments on a given day.
- **Availability**: The set of unbooked slots for a given doctor on a given date.

## Requirements

### Requirement 1: Book an Appointment

**User Story:** As a patient, I want to book a 30-minute appointment slot with a specific doctor, so that I can secure a confirmed visit time.

#### Acceptance Criteria

1. WHEN a patient submits a booking request via POST /appointments with a valid doctor, date, and time slot, THE Booking_System SHALL create an Appointment and return a confirmation response with HTTP status 201 containing the appointment ID, doctor ID, patient ID, date, time slot start time, and appointment status.
2. WHEN a booking request specifies a time slot that falls outside the doctor's Working_Hours, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating the slot is outside working hours.
3. WHEN a booking request specifies a time slot that is already taken by another Appointment, THE Booking_System SHALL reject the request and return HTTP status 409 with an error message indicating the slot is unavailable.
4. WHEN a booking request specifies a time slot in the past, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating past slots cannot be booked.
5. WHEN a booking request specifies a time slot within 1 hour of the current time, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating insufficient lead time.
6. WHEN an Appointment is created for a Slot, THE Booking_System SHALL mark that Slot as unavailable to all other patients.
7. WHEN a booking request specifies a doctor ID that does not exist in the system, THE Booking_System SHALL reject the request and return HTTP status 404 with an error message indicating the doctor was not found.
8. WHEN a booking request specifies a patient ID that does not exist in the system, THE Booking_System SHALL reject the request and return HTTP status 404 with an error message indicating the patient was not found.
9. WHEN a booking request specifies a time slot that does not align to a 30-minute boundary within the doctor's Working_Hours, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating the time slot must align to a valid 30-minute interval.

### Requirement 2: View Doctor Availability

**User Story:** As a patient, I want to see all available 30-minute slots for a specific doctor on a given date, so that I can choose a convenient appointment time.

#### Acceptance Criteria

1. WHEN a patient requests availability via GET /doctors/{id}/availability with a valid doctor ID and a date parameter, THE Booking_System SHALL return a list of all unbooked 30-minute Slots within the doctor's Working_Hours for that date, each slot represented by its start time, with HTTP status 200.
2. WHEN a patient requests availability for a doctor with no free slots on the specified date, THE Booking_System SHALL return an empty list with HTTP status 200.
3. WHEN a patient requests availability for a non-existent doctor ID, THE Booking_System SHALL return HTTP status 404 with an error message indicating the doctor was not found.
4. THE Booking_System SHALL compute available Slots by dividing the doctor's Working_Hours into consecutive 30-minute intervals and excluding intervals that have a non-cancelled Appointment.
5. IF a patient requests availability with a missing or malformed date parameter, THEN THE Booking_System SHALL return HTTP status 422 with an error message indicating the date is invalid.
6. WHEN a patient requests availability for today's date, THE Booking_System SHALL exclude Slots whose start time is less than 1 hour from the current time.
7. IF a patient requests availability for a past date, THEN THE Booking_System SHALL return an empty list with HTTP status 200.

### Requirement 3: Cancel an Appointment

**User Story:** As a patient, I want to cancel a booked appointment with a reason, so that the slot becomes available for other patients.

#### Acceptance Criteria

1. WHEN a patient submits a cancellation request via PATCH /appointments/{id}/cancel with a valid appointment ID and a cancellation reason between 1 and 500 characters, THE Booking_System SHALL mark the Appointment as cancelled, store the reason, and return HTTP status 200.
2. WHEN an Appointment is cancelled, THE Booking_System SHALL mark the associated Slot as available for booking by other patients.
3. WHEN a cancellation request targets an Appointment that is already cancelled, THE Booking_System SHALL return HTTP status 409 with an error message indicating the appointment is already cancelled.
4. WHEN a cancellation request targets a non-existent appointment ID, THE Booking_System SHALL return HTTP status 404 with an error message indicating the appointment was not found.
5. IF a cancellation request is submitted without a cancellation reason or with a reason that is empty or exceeds 500 characters, THEN THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating the reason is invalid.

### Requirement 4: Reschedule an Appointment

**User Story:** As a patient, I want to move an existing appointment to a different slot, so that I can adjust my schedule without losing my booking.

#### Acceptance Criteria

1. WHEN a patient submits a reschedule request via PATCH /appointments/{id}/reschedule with a valid appointment ID and a new time slot, THE Booking_System SHALL update the Appointment to the new Slot and return HTTP status 200.
2. WHEN an Appointment is rescheduled, THE Booking_System SHALL mark the original Slot as available for booking by other patients.
3. WHEN a reschedule request specifies a new Slot that falls outside the doctor's Working_Hours, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating the slot is outside working hours.
4. WHEN a reschedule request specifies a new Slot that is already taken by another Appointment, THE Booking_System SHALL reject the request and return HTTP status 409 with an error message indicating the slot is unavailable.
5. WHEN a reschedule request specifies a new Slot in the past, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating past slots cannot be booked.
6. WHEN a reschedule request specifies a new Slot within 1 hour of the current time, THE Booking_System SHALL reject the request and return HTTP status 422 with an error message indicating insufficient lead time.
7. WHEN a reschedule request targets an Appointment that is already cancelled, THE Booking_System SHALL return HTTP status 409 with an error message indicating cancelled appointments cannot be rescheduled.
8. WHEN a reschedule request targets a non-existent appointment ID, THE Booking_System SHALL return HTTP status 404 with an error message indicating the appointment was not found.

### Requirement 5: View Patient Appointments

**User Story:** As a patient, I want to view my upcoming appointments sorted by date, so that I can keep track of my scheduled visits.

#### Acceptance Criteria

1. WHEN a patient requests their appointments via GET /patients/{id}/appointments, THE Booking_System SHALL return a list of non-cancelled Appointments whose scheduled date and time are later than the current server time, sorted by date and time in ascending order, with HTTP status 200.
2. THE Booking_System SHALL include for each Appointment in the response: the appointment ID, doctor name, appointment date, start time, and appointment status.
3. WHEN a patient has no upcoming non-cancelled appointments, THE Booking_System SHALL return an empty list with HTTP status 200.
4. WHEN a request targets a non-existent patient ID, THE Booking_System SHALL return HTTP status 404 with an error message indicating the patient was not found.
5. IF the patient has more than 50 upcoming appointments, THEN THE Booking_System SHALL return only the nearest 50 appointments sorted by date and time in ascending order.

### Requirement 6: Doctor Working Hours Configuration

**User Story:** As a clinic administrator, I want each doctor to have defined working hours, so that the system correctly computes available slots.

#### Acceptance Criteria

1. THE Booking_System SHALL store Working_Hours for each Doctor including the days of the week and start/end times for each day.
2. THE Booking_System SHALL use a 30-minute interval to divide Working_Hours into bookable Slots.
3. WHEN a Doctor has no Working_Hours defined for a requested date, THE Booking_System SHALL return an empty availability list for that date.
4. IF Working_Hours start time is greater than or equal to end time for a given day, THEN THE Booking_System SHALL reject the configuration and return HTTP status 422 with an error message indicating invalid time range.
5. THE Booking_System SHALL only generate complete 30-minute Slots; partial intervals at the end of a Working_Hours period SHALL be excluded from availability.

### Requirement 7: Validation and Error Handling

**User Story:** As a developer, I want all validation failures to return meaningful error messages with correct HTTP status codes, so that API consumers can understand and resolve issues.

#### Acceptance Criteria

1. IF a request fails input validation (missing required fields, invalid field format, or values outside permitted ranges), THEN THE Booking_System SHALL return HTTP status 422 with a response body containing a "detail" field that identifies the invalid or missing field and the reason for rejection.
2. IF a request references a resource that does not exist (doctor, patient, or appointment ID not found), THEN THE Booking_System SHALL return HTTP status 404 with a response body containing a "detail" field that identifies which resource was not found.
3. IF a request conflicts with existing state (duplicate booking, cancelling an already-cancelled appointment, or rescheduling a cancelled appointment), THEN THE Booking_System SHALL return HTTP status 409 with a response body containing a "detail" field that describes the conflict.
4. IF a request body cannot be parsed as valid JSON, THEN THE Booking_System SHALL return HTTP status 422 with a response body containing a "detail" field indicating the request body is malformed.
5. THE Booking_System SHALL return all error responses with a consistent JSON structure containing at minimum a "detail" field of type string.

### Requirement 8: Deployment and CI/CD

**User Story:** As a developer, I want the application deployed to a cloud provider with automated testing and deployment, so that the system is publicly accessible and changes are delivered safely.

#### Acceptance Criteria

1. THE Booking_System SHALL be deployed to a cloud provider and reachable via a public URL that returns HTTP status 200 on a health check endpoint within 5 seconds.
2. WHEN a pull request is opened, THE CI/CD Pipeline SHALL run the full test suite and report the pass/fail status on the pull request within 10 minutes of the pipeline being triggered.
3. WHEN code is merged to the main branch, THE CI/CD Pipeline SHALL automatically deploy the updated application to the cloud provider within 10 minutes of the merge event.
4. IF the test suite fails during a pull request check, THEN THE CI/CD Pipeline SHALL block the merge of that pull request until the tests pass.

### Requirement 9: Code Structure and Test Coverage

**User Story:** As a developer, I want the code organized into logical modules with test coverage for booking logic, so that the system is maintainable and correct.

#### Acceptance Criteria

1. THE Booking_System SHALL separate concerns into distinct Python modules (separate files or packages) for routing, business logic, data access, and models, such that no single module contains logic belonging to more than one of these concerns.
2. THE Booking_System SHALL include automated tests covering the booking logic with at least one test case for each of the following areas: slot validation, conflict detection, and cancellation behavior, achieving a minimum of 80% line coverage on business logic modules.
3. WHEN a valid Appointment is cancelled, THE Booking_System SHALL show the original Slot as available in subsequent availability queries for the same doctor and date.
4. WHEN a valid booking request is accepted, THE Booking_System SHALL show the booked Slot as unavailable in subsequent availability queries for the same doctor and date.
