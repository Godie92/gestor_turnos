from django.contrib import admin
from .models import Booking, Service, Client


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'price', 'duration', 'is_active']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'tenant__name']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'phone', 'email', 'created_at']
    list_filter = ['tenant']
    search_fields = ['name', 'phone', 'email']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'service_name', 'tenant', 'start_time', 'status', 'price']
    list_filter = ['tenant', 'status']
    search_fields = ['client_name', 'service_name']
    list_editable = ['status']
