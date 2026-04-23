import datetime
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    color = models.CharField(max_length=20, default="#7c3aed")
    is_demo = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Membership(models.Model):
    PLAN_MONTHLY = 'monthly'
    PLAN_YEARLY = 'yearly'
    PLAN_CHOICES = [(PLAN_MONTHLY, 'Mensual'), (PLAN_YEARLY, 'Anual')]

    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_UNPAID = 'unpaid'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Prueba gratuita'),
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_UNPAID, 'Impaga'),
        (STATUS_EXPIRED, 'Vencida'),
    ]

    AMOUNT_MONTHLY = 5000
    AMOUNT_YEARLY = 50000

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='membership')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_MONTHLY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    start_date = models.DateField(default=datetime.date.today)
    end_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=AMOUNT_MONTHLY)
    mp_preference_id = models.CharField(max_length=255, blank=True)
    mp_payment_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant.name} — {self.get_status_display()}"

    @property
    def days_remaining(self):
        return (self.end_date - timezone.now().date()).days

    @property
    def is_expiring_soon(self):
        return 0 <= self.days_remaining <= 7

    @property
    def is_expired(self):
        return self.days_remaining < 0

    @property
    def status_color(self):
        colors = {
            self.STATUS_TRIAL: 'blue',
            self.STATUS_ACTIVE: 'green',
            self.STATUS_UNPAID: 'yellow',
            self.STATUS_EXPIRED: 'red',
        }
        return colors.get(self.status, 'gray')
