import urllib.parse
from django.db import models
from tenants.models import Tenant


class Service(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration = models.PositiveIntegerField(default=60, help_text='Duración en minutos')
    color = models.CharField(max_length=20, default='#7c3aed')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def duration_display(self):
        h, m = divmod(self.duration, 60)
        if h and m:
            return f'{h}h {m}min'
        if h:
            return f'{h}h'
        return f'{m}min'


class Client(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def whatsapp_url(self):
        if self.phone:
            clean = ''.join(c for c in self.phone if c.isdigit())
            return f'https://wa.me/{clean}'
        return None

    @property
    def total_bookings(self):
        return self.bookings.count()


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW = 'no_show'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_CONFIRMED, 'Confirmada'),
        (STATUS_COMPLETED, 'Completada'),
        (STATUS_CANCELLED, 'Cancelada'),
        (STATUS_NO_SHOW, 'No asistió'),
    ]

    STATUS_COLORS = {
        STATUS_PENDING: '#f59e0b',
        STATUS_CONFIRMED: '#3b82f6',
        STATUS_COMPLETED: '#22c55e',
        STATUS_CANCELLED: '#ef4444',
        STATUS_NO_SHOW: '#6b7280',
    }

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    client_name = models.CharField(max_length=255)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    service_name = models.CharField(max_length=255)
    staff = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.client_name} — {self.service_name} ({self.start_time:%d/%m %H:%M})'

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, '#6b7280')

    @property
    def duration_minutes(self):
        return int((self.end_time - self.start_time).total_seconds() / 60)

    def whatsapp_reminder_url(self):
        phone = self.client.phone if self.client else ''
        if not phone:
            return None
        clean = ''.join(c for c in phone if c.isdigit())
        text = (
            f'Hola {self.client_name}! Te recordamos tu turno '
            f'el {self.start_time.strftime("%d/%m")} a las {self.start_time.strftime("%H:%M")} '
            f'para {self.service_name}. ¡Te esperamos!'
        )
        return f'https://wa.me/{clean}?text={urllib.parse.quote(text)}'
