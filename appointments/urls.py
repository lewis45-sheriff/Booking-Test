"""URL configuration for the appointments app."""
from django.urls import path

from .views import (
    # Booking endpoints
    AppointmentBookView,
    AppointmentCancelView,
    AppointmentRescheduleView,
    DoctorAvailabilityView,
    HealthCheckView,
    PatientAppointmentsView,
    # Registration endpoints
    DoctorRegisterView,
    DoctorListView,
    DoctorDetailView,
    PatientRegisterView,
    PatientListView,
    WorkingHoursConfigView,
    DoctorWorkingHoursListView,
)

urlpatterns = [
    # --- Booking & Scheduling ---
    path('appointments', AppointmentBookView.as_view(), name='appointment-book'),
    path('appointments/<uuid:appointment_id>/cancel', AppointmentCancelView.as_view(), name='appointment-cancel'),
    path('appointments/<uuid:appointment_id>/reschedule', AppointmentRescheduleView.as_view(), name='appointment-reschedule'),
    path('doctors/<uuid:doctor_id>/availability', DoctorAvailabilityView.as_view(), name='doctor-availability'),
    path('patients/<uuid:patient_id>/appointments', PatientAppointmentsView.as_view(), name='patient-appointments'),

    # --- Doctor Registration & Configuration ---
    path('doctors', DoctorRegisterView.as_view(), name='doctor-register'),
    path('doctors/list', DoctorListView.as_view(), name='doctor-list'),
    path('doctors/<uuid:doctor_id>', DoctorDetailView.as_view(), name='doctor-detail'),
    path('doctors/<uuid:doctor_id>/working-hours', DoctorWorkingHoursListView.as_view(), name='doctor-working-hours'),
    path('working-hours', WorkingHoursConfigView.as_view(), name='working-hours-config'),

    # --- Patient Registration ---
    path('patients', PatientRegisterView.as_view(), name='patient-register'),
    path('patients/list', PatientListView.as_view(), name='patient-list'),

    # --- Health ---
    path('health', HealthCheckView.as_view(), name='health-check'),
]
