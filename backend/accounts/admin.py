from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'tenant', 'role', 'is_active']
    list_filter = ['role', 'tenant']
    fieldsets = UserAdmin.fieldsets + (
        ('Salon Pro', {'fields': ('tenant', 'role')}),
    )
