"""DRF views for the appointments app."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers, status
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

from appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AppointmentListSerializer,
    AvailabilitySerializer,
    CancelSerializer,
    CancelResponseSerializer,
    RescheduleSerializer,
    PatientAppointmentSerializer,
)
from appointments.services.booking import create_booking
from appointments.services.cancellation import cancel_appointment
from appointments.services.reschedule import reschedule_appointment
from appointments.services.availability import get_availability
from appointments.services.patient_service import list_upcoming_appointments


# ---------------------------------------------------------------------------
# Error response serializer (for documentation only)
# ---------------------------------------------------------------------------

class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response format."""
    detail = serializers.CharField(help_text="Human-readable error message")


# ---------------------------------------------------------------------------
# Appointment Endpoints
# ---------------------------------------------------------------------------


class AppointmentBookView(APIView):
    """Book a new 30-minute appointment slot with a doctor."""

    @extend_schema(
        tags=["Appointments"],
        summary="Book an appointment",
        description=(
            "Create a new 30-minute appointment for a patient with a specific doctor.\n\n"
            "**Validation rules:**\n"
            "- The slot must be within the doctor's working hours\n"
            "- The slot must be aligned to a 30-minute boundary (:00 or :30)\n"
            "- The slot must be at least 1 hour in the future\n"
            "- The slot must not already be booked by another patient\n"
            "- Both doctor and patient must exist in the system"
        ),
        request=AppointmentCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=AppointmentSerializer,
                description="Appointment booked successfully",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Doctor or patient not found",
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Slot is already booked by another appointment",
            ),
            422: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error (outside hours, past slot, insufficient lead time, non-aligned)",
            ),
        },
        examples=[
            OpenApiExample(
                "Valid booking request",
                value={
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "patient_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "appointment_date": "2025-07-14",
                    "start_time": "10:00",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Successful response",
                value={
                    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "patient_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "appointment_date": "2025-07-14",
                    "start_time": "10:00",
                    "status": "scheduled",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = create_booking(**serializer.validated_data)
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class AppointmentCancelView(APIView):
    """Cancel an existing appointment."""

    @extend_schema(
        tags=["Appointments"],
        summary="Cancel an appointment",
        description=(
            "Mark an appointment as cancelled and record the reason.\n\n"
            "Once cancelled, the slot becomes available for other patients to book.\n"
            "An already-cancelled appointment cannot be cancelled again (409).\n\n"
            "**Cancellation reason rules:**\n"
            "- Must be between 1 and 500 characters\n"
            "- Cannot be empty or missing"
        ),
        request=CancelSerializer,
        responses={
            200: OpenApiResponse(
                response=CancelResponseSerializer,
                description="Appointment cancelled successfully",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Appointment not found",
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Appointment is already cancelled",
            ),
            422: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid or missing cancellation reason",
            ),
        },
        examples=[
            OpenApiExample(
                "Cancel request",
                value={"cancellation_reason": "Schedule conflict — need to reschedule"},
                request_only=True,
            ),
            OpenApiExample(
                "Cancelled response",
                value={
                    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "patient_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "appointment_date": "2025-07-14",
                    "start_time": "10:00",
                    "status": "cancelled",
                    "cancellation_reason": "Schedule conflict — need to reschedule",
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def patch(self, request, appointment_id):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = cancel_appointment(
            appointment_id,
            serializer.validated_data["cancellation_reason"],
        )
        return Response(
            CancelResponseSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )


class AppointmentRescheduleView(APIView):
    """Move an existing appointment to a different time slot."""

    @extend_schema(
        tags=["Appointments"],
        summary="Reschedule an appointment",
        description=(
            "Move an appointment to a new date and time slot.\n\n"
            "The original slot is freed and becomes available for other patients.\n"
            "All booking validation rules apply to the new slot (working hours, "
            "alignment, lead time, conflict check).\n\n"
            "**Cannot reschedule if:**\n"
            "- The appointment is already cancelled (409)\n"
            "- The new slot is already taken (409)\n"
            "- The new slot fails validation (422)"
        ),
        request=RescheduleSerializer,
        responses={
            200: OpenApiResponse(
                response=AppointmentSerializer,
                description="Appointment rescheduled successfully",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Appointment not found",
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="New slot is taken or appointment is cancelled",
            ),
            422: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="New slot fails validation (outside hours, past, etc.)",
            ),
        },
        examples=[
            OpenApiExample(
                "Reschedule request",
                value={"appointment_date": "2025-07-15", "start_time": "14:00"},
                request_only=True,
            ),
            OpenApiExample(
                "Rescheduled response",
                value={
                    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "patient_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "appointment_date": "2025-07-15",
                    "start_time": "14:00",
                    "status": "scheduled",
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def patch(self, request, appointment_id):
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = reschedule_appointment(
            appointment_id,
            serializer.validated_data["appointment_date"],
            serializer.validated_data["start_time"],
        )
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Availability Endpoint
# ---------------------------------------------------------------------------


class DoctorAvailabilityView(APIView):
    """View available appointment slots for a doctor on a specific date."""

    @extend_schema(
        tags=["Availability"],
        summary="Get doctor availability",
        description=(
            "Returns all available 30-minute appointment slots for a doctor on the "
            "specified date.\n\n"
            "**Slot computation:**\n"
            "- Divides the doctor's working hours into consecutive 30-minute intervals\n"
            "- Excludes slots that are already booked\n"
            "- For today's date, excludes slots less than 1 hour from now\n"
            "- Returns an empty list for past dates or days with no working hours"
        ),
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=True,
                description="The date to check availability for (format: YYYY-MM-DD)",
                examples=[
                    OpenApiExample("Example date", value="2025-07-14"),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AvailabilitySerializer,
                description="List of available time slots (may be empty)",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Doctor not found",
            ),
            422: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Missing or malformed date parameter",
            ),
        },
        examples=[
            OpenApiExample(
                "Available slots",
                value={"slots": ["09:00", "09:30", "10:30", "11:00", "14:00", "14:30", "15:00"]},
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "No availability",
                value={"slots": []},
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, doctor_id):
        raw_date = request.query_params.get("date")
        try:
            if raw_date is None:
                raise serializers.ValidationError("date is required")
            query_date = serializers.DateField().run_validation(raw_date)
        except (serializers.ValidationError, Exception):
            return Response(
                {"detail": "A valid date is required (YYYY-MM-DD)."},
                status=422,
            )

        slots = get_availability(doctor_id, query_date)
        return Response(
            {"slots": [slot.strftime("%H:%M") for slot in slots]},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Patient Appointments Endpoint
# ---------------------------------------------------------------------------


class PatientAppointmentsView(APIView):
    """View a patient's upcoming scheduled appointments."""

    @extend_schema(
        tags=["Patients"],
        summary="List upcoming appointments",
        description=(
            "Returns up to 50 upcoming non-cancelled appointments for the patient, "
            "sorted by date and time in ascending order.\n\n"
            "**Filtering:**\n"
            "- Only includes appointments with status 'scheduled'\n"
            "- Only includes appointments whose date/time is strictly after now\n"
            "- Capped at 50 results (nearest appointments first)"
        ),
        responses={
            200: OpenApiResponse(
                response=PatientAppointmentSerializer(many=True),
                description="List of upcoming appointments (may be empty)",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Patient not found",
            ),
        },
        examples=[
            OpenApiExample(
                "Upcoming appointments",
                value=[
                    {
                        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                        "doctor_name": "Dr. Smith",
                        "appointment_date": "2025-07-14",
                        "start_time": "10:00",
                        "status": "scheduled",
                    },
                    {
                        "id": "d4e5f6a7-b890-1234-defg-234567890123",
                        "doctor_name": "Dr. Johnson",
                        "appointment_date": "2025-07-21",
                        "start_time": "14:30",
                        "status": "scheduled",
                    },
                ],
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, patient_id):
        appointments = list_upcoming_appointments(patient_id)
        return Response(
            PatientAppointmentSerializer(appointments, many=True).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# All Appointments (Paginated)
# ---------------------------------------------------------------------------


class AppointmentListView(APIView):
    """List all appointments with pagination."""

    @extend_schema(
        tags=["Appointments"],
        summary="List all appointments (paginated)",
        description=(
            "Returns a paginated list of all appointments in the system.\n\n"
            "**Query parameters:**\n"
            "- `page` (default: 1) — page number\n"
            "- `page_size` (default: 20, max: 100) — items per page\n"
            "- `status` (optional) — filter by status: 'scheduled' or 'cancelled'"
        ),
        parameters=[
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number (default: 1)",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Items per page (default: 20, max: 100)",
            ),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by status: 'scheduled' or 'cancelled'",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Paginated list of appointments",
            ),
        },
    )
    def get(self, request):
        from appointments.models import Appointment

        # Parse pagination params
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
        except (ValueError, TypeError):
            page_size = 20

        # Filter by status if provided
        status_filter = request.query_params.get("status")
        queryset = Appointment.objects.select_related("doctor", "patient").order_by(
            "-appointment_date", "-start_time"
        )
        if status_filter in ("scheduled", "cancelled"):
            queryset = queryset.filter(status=status_filter)

        # Paginate
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        appointments = queryset[start:end]

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
                "results": AppointmentListSerializer(appointments, many=True).data,
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class HealthCheckView(APIView):
    """System health check endpoint."""

    @extend_schema(
        tags=["Health"],
        summary="Health check",
        description="Returns a simple status indicating the API is running and responsive.",
        responses={
            200: OpenApiResponse(
                description="System is healthy",
                examples=[
                    OpenApiExample(
                        "Healthy",
                        value={"status": "ok"},
                    ),
                ],
            ),
        },
    )
    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Registration Endpoints
# ---------------------------------------------------------------------------

from appointments.serializers import (
    DoctorCreateSerializer,
    DoctorSerializer,
    DoctorListSerializer,
    PatientCreateSerializer,
    PatientSerializer,
    WorkingHoursCreateSerializer,
    WorkingHoursSerializer,
)
from appointments.models import Doctor, Patient, WorkingHours


class DoctorRegisterView(APIView):
    """Register a new doctor in the system."""

    @extend_schema(
        tags=["Doctors"],
        summary="Register a doctor",
        description=(
            "Create a new doctor record in the system.\n\n"
            "After registration, configure the doctor's working hours using "
            "the working hours endpoint."
        ),
        request=DoctorCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=DoctorSerializer,
                description="Doctor registered successfully",
            ),
        },
        examples=[
            OpenApiExample(
                "Register a doctor",
                value={"name": "Dr. Sarah Johnson", "specialty": "Dermatology"},
                request_only=True,
            ),
            OpenApiExample(
                "Doctor registered",
                value={
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "name": "Dr. Sarah Johnson",
                    "specialty": "Dermatology",
                    "created_at": "2025-07-10T08:30:00Z",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = DoctorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doctor = serializer.save()
        return Response(
            DoctorSerializer(doctor).data,
            status=status.HTTP_201_CREATED,
        )


class DoctorListView(APIView):
    """List all registered doctors."""

    @extend_schema(
        tags=["Doctors"],
        summary="List all doctors",
        description="Returns a list of all doctors registered in the system.",
        responses={
            200: OpenApiResponse(
                response=DoctorListSerializer(many=True),
                description="List of doctors",
            ),
        },
    )
    def get(self, request):
        doctors = Doctor.objects.all().order_by("name")
        return Response(
            DoctorListSerializer(doctors, many=True).data,
            status=status.HTTP_200_OK,
        )


class DoctorDetailView(APIView):
    """Get a single doctor's details including working hours."""

    @extend_schema(
        tags=["Doctors"],
        summary="Get doctor details",
        description="Returns a doctor's profile and their configured working hours.",
        responses={
            200: OpenApiResponse(
                response=DoctorSerializer,
                description="Doctor details",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Doctor not found",
            ),
        },
    )
    def get(self, request, doctor_id):
        from appointments.repositories.doctor_repo import DoctorRepo

        doctor = DoctorRepo().get_by_id(doctor_id)
        working_hours = WorkingHours.objects.filter(doctor=doctor).order_by("day_of_week")

        data = DoctorSerializer(doctor).data
        data["working_hours"] = WorkingHoursSerializer(working_hours, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class PatientRegisterView(APIView):
    """Register a new patient in the system."""

    @extend_schema(
        tags=["Patients"],
        summary="Register a patient",
        description=(
            "Create a new patient record. Email must be unique across all patients."
        ),
        request=PatientCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=PatientSerializer,
                description="Patient registered successfully",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error (e.g. duplicate email)",
            ),
        },
        examples=[
            OpenApiExample(
                "Register a patient",
                value={
                    "name": "Jane Doe",
                    "email": "jane.doe@example.com",
                    "phone": "+254712345678",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Patient registered",
                value={
                    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "name": "Jane Doe",
                    "email": "jane.doe@example.com",
                    "phone": "+254712345678",
                    "created_at": "2025-07-10T09:00:00Z",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = PatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            patient = serializer.save()
        except Exception:
            return Response(
                {"detail": "A patient with this email already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            PatientSerializer(patient).data,
            status=status.HTTP_201_CREATED,
        )


class PatientListView(APIView):
    """List all registered patients."""

    @extend_schema(
        tags=["Patients"],
        summary="List all patients",
        description="Returns a list of all patients registered in the system.",
        responses={
            200: OpenApiResponse(
                response=PatientSerializer(many=True),
                description="List of patients",
            ),
        },
    )
    def get(self, request):
        patients = Patient.objects.all().order_by("name")
        return Response(
            PatientSerializer(patients, many=True).data,
            status=status.HTTP_200_OK,
        )


class WorkingHoursConfigView(APIView):
    """Configure working hours for a doctor."""

    @extend_schema(
        tags=["Doctors"],
        summary="Set working hours",
        description=(
            "Configure a doctor's working hours for a specific day of the week.\n\n"
            "**Day of week values:**\n"
            "- 0 = Monday\n"
            "- 1 = Tuesday\n"
            "- 2 = Wednesday\n"
            "- 3 = Thursday\n"
            "- 4 = Friday\n"
            "- 5 = Saturday\n"
            "- 6 = Sunday\n\n"
            "Each doctor can have at most one working hours entry per day. "
            "Sending a new entry for an existing day will return a conflict error."
        ),
        request=WorkingHoursCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=WorkingHoursSerializer,
                description="Working hours configured successfully",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Doctor not found",
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Working hours already configured for this day",
            ),
            422: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid time range (start_time must be before end_time)",
            ),
        },
        examples=[
            OpenApiExample(
                "Set Monday hours",
                value={
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Working hours saved",
                value={
                    "id": "e5f6a7b8-9012-3456-cdef-567890abcdef",
                    "doctor_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = WorkingHoursCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Verify doctor exists
        from appointments.repositories.doctor_repo import DoctorRepo

        doctor_id = serializer.validated_data["doctor_id"]
        DoctorRepo().get_by_id(doctor_id)

        try:
            wh = WorkingHours.objects.create(
                doctor_id=doctor_id,
                day_of_week=serializer.validated_data["day_of_week"],
                start_time=serializer.validated_data["start_time"],
                end_time=serializer.validated_data["end_time"],
            )
        except Exception:
            return Response(
                {"detail": "Working hours already configured for this doctor on this day."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            WorkingHoursSerializer(wh).data,
            status=status.HTTP_201_CREATED,
        )


class DoctorWorkingHoursListView(APIView):
    """List all working hours for a specific doctor."""

    @extend_schema(
        tags=["Doctors"],
        summary="Get doctor's working hours",
        description="Returns all configured working hours for a doctor, ordered by day of week.",
        responses={
            200: OpenApiResponse(
                response=WorkingHoursSerializer(many=True),
                description="List of working hours",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Doctor not found",
            ),
        },
    )
    def get(self, request, doctor_id):
        from appointments.repositories.doctor_repo import DoctorRepo

        DoctorRepo().get_by_id(doctor_id)
        working_hours = WorkingHours.objects.filter(doctor_id=doctor_id).order_by("day_of_week")
        return Response(
            WorkingHoursSerializer(working_hours, many=True).data,
            status=status.HTTP_200_OK,
        )
