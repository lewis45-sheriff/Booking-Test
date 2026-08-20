"""URL configuration for the appointments app."""
from django.urls import path

from .views import (AppointmentBookView,AppointmentCancelView,AppointmentRescheduleView,DoctorAvailabilityView,HealthCheckView,PatientAppointmentsView,)

urlpatterns = [
    path('appointments', AppointmentBookView.as_view(), name='appointment-book'),
    path('appointments/<uuid:appointment_id>/cancel', AppointmentCancelView.as_view(), name='appointment-cancel'),
    path('appointments/<uuid:appointment_id>/reschedule', AppointmentRescheduleView.as_view(), name='appointment-reschedule'),
    path('doctors/<uuid:doctor_id>/availability', DoctorAvailabilityView.as_view(), name='doctor-availability'),
    path('patients/<uuid:patient_id>/appointments', PatientAppointmentsView.as_view(), name='patient-appointments'),
    path('health', HealthCheckView.as_view(), name='health-check'),
]
