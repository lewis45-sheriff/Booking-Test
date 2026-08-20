"""DRF serializers for the appointments app."""
from rest_framework import serializers

from .models import Appointment


class AppointmentCreateSerializer(serializers.Serializer):
    """Deserializes and validates incoming booking requests."""

    doctor_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"])


class AppointmentSerializer(serializers.ModelSerializer):
    """Response serializer for booking and reschedule operations."""

    class Meta:
        model = Appointment
        fields = ["id", "doctor_id", "patient_id", "appointment_date", "start_time", "status"]


class CancelSerializer(serializers.Serializer):
    """Deserializes and validates cancellation requests."""

    cancellation_reason = serializers.CharField(min_length=1, max_length=500)


class CancelResponseSerializer(serializers.ModelSerializer):
    """Response serializer for cancellation — includes cancellation_reason."""

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor_id",
            "patient_id",
            "appointment_date",
            "start_time",
            "status",
            "cancellation_reason",
        ]


class RescheduleSerializer(serializers.Serializer):
    """Deserializes and validates reschedule requests."""

    appointment_date = serializers.DateField()
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"])


class AvailabilitySerializer(serializers.Serializer):
    """Serializes a list of available time slots."""

    slots = serializers.ListField(child=serializers.TimeField(format="%H:%M"))


class PatientAppointmentSerializer(serializers.ModelSerializer):
    """
    Response serializer for the patient's upcoming appointments list.

    Required fields per Requirement 5.2:
      - appointment ID
      - doctor name
      - appointment date
      - start time
      - status
    """

    doctor_name = serializers.CharField(source="doctor.name", read_only=True)

    class Meta:
        model = Appointment
        fields = ["id", "doctor_name", "appointment_date", "start_time", "status"]
