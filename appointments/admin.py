"""Django admin registrations for the appointments app."""
from django.contrib import admin

from .models import Appointment, Doctor, Patient, WorkingHours

admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(WorkingHours)
admin.site.register(Appointment)
