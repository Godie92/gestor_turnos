import datetime
from django.contrib import admin
from django.utils.html import format_html
from .models import Tenant, Membership


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'color', 'is_demo']
    search_fields = ['name', 'subdomain']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status_badge', 'end_date', 'days_left', 'amount']
    list_filter = ['status', 'plan']
    search_fields = ['tenant__name']
    actions = ['mark_as_paid', 'mark_as_unpaid']

    def status_badge(self, obj):
        colors = {
            'trial': '#3b82f6',
            'active': '#22c55e',
            'unpaid': '#f59e0b',
            'expired': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:9999px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    def days_left(self, obj):
        days = obj.days_remaining
        if days < 0:
            return format_html('<span style="color:red">Vencida hace {} días</span>', abs(days))
        if days <= 7:
            return format_html('<span style="color:orange">{} días</span>', days)
        return f'{days} días'
    days_left.short_description = 'Días restantes'

    def mark_as_paid(self, request, queryset):
        for m in queryset:
            m.status = Membership.STATUS_ACTIVE
            m.start_date = datetime.date.today()
            delta = datetime.timedelta(days=365 if m.plan == 'yearly' else 30)
            m.end_date = datetime.date.today() + delta
            m.save()
        self.message_user(request, f'{queryset.count()} membresías marcadas como pagadas.')
    mark_as_paid.short_description = 'Marcar como pagada'

    def mark_as_unpaid(self, request, queryset):
        queryset.update(status=Membership.STATUS_UNPAID)
        self.message_user(request, f'{queryset.count()} membresías marcadas como impagas.')
    mark_as_unpaid.short_description = 'Marcar como impaga'
