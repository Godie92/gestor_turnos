from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'service', 'tenant', 'start_time', 'end_time']
    list_filter = ['tenant']
    search_fields = ['client_name', 'service']
