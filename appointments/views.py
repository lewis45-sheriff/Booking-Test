"""DRF views for the appointments app."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers, status

from appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
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


class AppointmentBookView(APIView):
    """POST /appointments — Book a new appointment."""

    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = create_booking(**serializer.validated_data)
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class AppointmentCancelView(APIView):
    """PATCH /appointments/{appointment_id}/cancel — Cancel an appointment."""

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
    """PATCH /appointments/{appointment_id}/reschedule — Reschedule an appointment."""

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


class DoctorAvailabilityView(APIView):
    """GET /doctors/{doctor_id}/availability?date=YYYY-MM-DD — View available slots."""

    def get(self, request, doctor_id):
        # Validate the required `date` query parameter.
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


class PatientAppointmentsView(APIView):
    """GET /patients/{patient_id}/appointments — List upcoming appointments."""

    def get(self, request, patient_id):
        appointments = list_upcoming_appointments(patient_id)
        return Response(
            PatientAppointmentSerializer(appointments, many=True).data,
            status=status.HTTP_200_OK,
        )


class HealthCheckView(APIView):
    """GET /health — Simple health check endpoint."""

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
