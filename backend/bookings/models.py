
# Create your models here.
from django.db import models
from tenants.models import Tenant

class Booking(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    client_name = models.CharField(max_length=255)
    service = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
