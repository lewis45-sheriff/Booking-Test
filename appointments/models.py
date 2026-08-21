"""Django ORM models for the appointments app."""
import uuid
from django.db import models


class Doctor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=320, unique=True)
    phone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        Doctor, on_delete=models.CASCADE, related_name="working_hours"
    )
    day_of_week = models.SmallIntegerField()  # 0=Monday … 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = [("doctor", "day_of_week")]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="wh_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.doctor.name} — day {self.day_of_week} ({self.start_time}–{self.end_time})"


class Appointment(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="appointments"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="appointments"
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    cancellation_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # The partial unique index is added via a RunSQL migration step (Task 2.2)
        constraints = []

    def __str__(self):
        return f"Appointment {self.id} — {self.doctor.name} / {self.patient.name} @ {self.appointment_date} {self.start_time}"
