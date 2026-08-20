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


# ---------------------------------------------------------------------------
# Registration serializers
# ---------------------------------------------------------------------------

from .models import Doctor, Patient, WorkingHours


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Create a new doctor."""

    class Meta:
        model = Doctor
        fields = ["id", "name", "specialty"]
        read_only_fields = ["id"]


class DoctorSerializer(serializers.ModelSerializer):
    """Full doctor response."""

    class Meta:
        model = Doctor
        fields = ["id", "name", "specialty", "created_at"]


class PatientCreateSerializer(serializers.ModelSerializer):
    """Register a new patient."""

    class Meta:
        model = Patient
        fields = ["id", "name", "email", "phone"]
        read_only_fields = ["id"]


class PatientSerializer(serializers.ModelSerializer):
    """Full patient response."""

    class Meta:
        model = Patient
        fields = ["id", "name", "email", "phone", "created_at"]


class WorkingHoursCreateSerializer(serializers.Serializer):
    """Configure working hours for a doctor on a specific day."""

    doctor_id = serializers.UUIDField()
    day_of_week = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError(
                "Working hours start_time must be before end_time."
            )
        return data


class WorkingHoursSerializer(serializers.ModelSerializer):
    """Full working hours response."""

    class Meta:
        model = WorkingHours
        fields = ["id", "doctor_id", "day_of_week", "start_time", "end_time"]


class DoctorListSerializer(serializers.ModelSerializer):
    """Doctor list with working hours summary."""

    class Meta:
        model = Doctor
        fields = ["id", "name", "specialty", "created_at"]
