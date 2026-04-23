
# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from tenants.models import Tenant

class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    role = models.CharField(max_length=20)
