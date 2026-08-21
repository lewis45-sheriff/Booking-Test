# Generated migration for the clinic booking system
# Task 2.2: Initial migration with partial unique index and check constraint

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ── Doctor ──────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Doctor",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("specialty", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        # ── Patient ─────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Patient",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=320, unique=True)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        # ── WorkingHours ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkingHours",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "doctor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="working_hours",
                        to="appointments.doctor",
                    ),
                ),
                ("day_of_week", models.SmallIntegerField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
            ],
        ),
        # unique_together on WorkingHours (doctor, day_of_week)
        migrations.AlterUniqueTogether(
            name="workinghours",
            unique_together={("doctor", "day_of_week")},
        ),
        # CHECK constraint: end_time > start_time  (Requirement 6.4)
        # Django 5.1+ renamed the 'check' kwarg to 'condition'
        migrations.AddConstraint(
            model_name="workinghours",
            constraint=models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="wh_end_after_start",
            ),
        ),
        # ── Appointment ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Appointment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "doctor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="appointments.doctor",
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="appointments.patient",
                    ),
                ),
                ("appointment_date", models.DateField()),
                ("start_time", models.TimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                ("cancellation_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        # Partial unique index — DB-level safety net against double-booking
        # (Requirement 1.3): only non-cancelled appointments occupy a slot.
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX uq_appointment_slot_active "
                "ON appointments_appointment (doctor_id, appointment_date, start_time) "
                "WHERE status != 'cancelled';"
            ),
            reverse_sql="DROP INDEX IF EXISTS uq_appointment_slot_active;",
        ),
    ]
