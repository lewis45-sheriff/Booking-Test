"""Root URL configuration for the clinic_booking project."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('appointments.urls')),
]
