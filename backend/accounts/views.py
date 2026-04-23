import random
import datetime
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import LoginForm, RegisterSalonForm
from .models import User
from tenants.models import Tenant, Membership
from bookings.models import Booking

DEMO_CLIENTS = [
    'María García', 'Laura Martínez', 'Ana López', 'Carla Rodríguez', 'Sofía Fernández',
    'Isabella Torres', 'Valentina Gómez', 'Lucía Pérez', 'Martina Díaz', 'Emma Sánchez',
    'Diego Romero', 'Camila Silva', 'Agustina Molina', 'Florencia Ruiz', 'Natalia Vega',
]


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterSalonForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tenant = Tenant.objects.create(
            name=form.cleaned_data['salon_name'],
            subdomain=form.cleaned_data['subdomain'],
        )
        Membership.objects.create(
            tenant=tenant,
            status=Membership.STATUS_TRIAL,
            plan=Membership.PLAN_MONTHLY,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=14),
            amount=Membership.AMOUNT_MONTHLY,
        )
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
            tenant=tenant,
            role='owner',
        )
        login(request, user)
        return redirect('dashboard')
    return render(request, 'accounts/register.html', {'form': form})


def demo_view(request):
    tenant, _ = Tenant.objects.get_or_create(
        subdomain='salon-demo',
        defaults={'name': 'Salón Demo', 'is_demo': True, 'color': '#7c3aed'},
    )
    tenant.is_demo = True
    tenant.save(update_fields=['is_demo'])

    membership, _ = Membership.objects.get_or_create(
        tenant=tenant,
        defaults={
            'status': Membership.STATUS_ACTIVE,
            'plan': Membership.PLAN_MONTHLY,
            'start_date': datetime.date.today(),
            'end_date': datetime.date.today() + datetime.timedelta(days=30),
            'amount': Membership.AMOUNT_MONTHLY,
        },
    )

    user, created = User.objects.get_or_create(
        username='demo',
        defaults={
            'email': 'demo@salonpro.com',
            'tenant': tenant,
            'role': 'owner',
        },
    )
    if created:
        user.set_password('demo123')
        user.save()
    user.tenant = tenant
    user.save(update_fields=['tenant'])

    _populate_demo_bookings(tenant)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('dashboard')


def _populate_demo_bookings(tenant):
    demo_services = settings.APP_CONFIG.get('demo_services', ['Servicio A', 'Servicio B', 'Servicio C'])
    Booking.objects.filter(tenant=tenant).delete()
    today = timezone.now().date()
    bookings = []
    for day_offset in range(7):
        day = today + datetime.timedelta(days=day_offset)
        for hour in random.sample(range(9, 19), random.randint(3, 6)):
            start = timezone.make_aware(
                datetime.datetime.combine(day, datetime.time(hour, 0))
            )
            bookings.append(Booking(
                tenant=tenant,
                client_name=random.choice(DEMO_CLIENTS),
                service=random.choice(demo_services),
                start_time=start,
                end_time=start + datetime.timedelta(hours=1),
            ))
    Booking.objects.bulk_create(bookings)


@login_required
def dashboard_view(request):
    today = timezone.now().date()
    tenant = request.user.tenant
    bookings_today = Booking.objects.filter(
        tenant=tenant, start_time__date=today,
    ).order_by('start_time')
    upcoming = Booking.objects.filter(
        tenant=tenant, start_time__gte=timezone.now(),
    ).order_by('start_time')[:5]
    total = Booking.objects.filter(tenant=tenant).count()
    membership = getattr(tenant, 'membership', None)
    return render(request, 'dashboard.html', {
        'bookings_today': bookings_today,
        'upcoming': upcoming,
        'total': total,
        'today_count': bookings_today.count(),
        'membership': membership,
    })
