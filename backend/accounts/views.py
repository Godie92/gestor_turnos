import random
import datetime
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import LoginForm, RegisterSalonForm, ProfileForm, StaffForm
from .models import User
from tenants.models import Tenant, Membership
from bookings.models import Booking, Service, Client

DEMO_CLIENTS = [
    'María García', 'Laura Martínez', 'Ana López', 'Carla Rodríguez', 'Sofía Fernández',
    'Isabella Torres', 'Valentina Gómez', 'Lucía Pérez', 'Martina Díaz', 'Emma Sánchez',
    'Diego Romero', 'Camila Silva', 'Agustina Molina', 'Florencia Ruiz', 'Natalia Vega',
]
DEMO_PHONES = [
    '+54 9 11 2345-6789', '+54 9 11 3456-7890', '+54 9 11 4567-8901',
    '+54 9 11 5678-9012', '+54 9 11 6789-0123', '',
]


def login_view(request):
    if request.user.is_authenticated:
        return redirect('superadmin_panel' if request.user.is_staff else 'dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('superadmin_panel' if user.is_staff else 'dashboard')
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
        defaults={'name': 'Negocio Demo', 'is_demo': True, 'color': '#7c3aed'},
    )
    tenant.is_demo = True
    tenant.save(update_fields=['is_demo'])

    Membership.objects.get_or_create(
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
        defaults={'email': 'demo@app.com', 'tenant': tenant, 'role': 'owner'},
    )
    if created:
        user.set_password('demo123')
        user.save()
    user.tenant = tenant
    user.save(update_fields=['tenant'])

    _populate_demo_data(tenant)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('dashboard')


def _populate_demo_data(tenant):
    demo_services_cfg = settings.APP_CONFIG.get('demo_services', [
        'Servicio A', 'Servicio B', 'Servicio C'
    ])

    # Create demo services if none exist
    if not Service.objects.filter(tenant=tenant).exists():
        colors = ['#7c3aed', '#3b82f6', '#ec4899', '#f59e0b', '#22c55e', '#ef4444', '#8b5cf6', '#06b6d4']
        for i, name in enumerate(demo_services_cfg):
            Service.objects.create(
                tenant=tenant, name=name, price=random.randint(1500, 8000),
                duration=random.choice([30, 45, 60, 90]),
                color=colors[i % len(colors)], order=i,
            )

    services = list(Service.objects.filter(tenant=tenant))

    # Create demo clients if none exist
    if not Client.objects.filter(tenant=tenant).exists():
        for i, name in enumerate(DEMO_CLIENTS):
            Client.objects.create(
                tenant=tenant, name=name,
                phone=DEMO_PHONES[i % len(DEMO_PHONES)],
                email=f'{name.lower().replace(" ", ".")}@demo.com' if i % 3 != 0 else '',
            )

    clients = list(Client.objects.filter(tenant=tenant))

    # Reset and recreate bookings
    Booking.objects.filter(tenant=tenant).delete()
    today = timezone.now().date()
    statuses = ['pending', 'confirmed', 'completed', 'completed', 'confirmed']
    bookings = []
    for day_offset in range(-3, 8):
        day = today + datetime.timedelta(days=day_offset)
        for hour in random.sample(range(9, 19), random.randint(3, 6)):
            start = timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, 0)))
            svc = random.choice(services) if services else None
            cli = random.choice(clients) if clients else None
            status = 'completed' if day_offset < 0 else random.choice(statuses)
            bookings.append(Booking(
                tenant=tenant,
                client=cli,
                client_name=cli.name if cli else random.choice(DEMO_CLIENTS),
                service=svc,
                service_name=svc.name if svc else 'Servicio',
                start_time=start,
                end_time=start + datetime.timedelta(minutes=svc.duration if svc else 60),
                status=status,
                price=float(svc.price) if svc else None,
            ))
    Booking.objects.bulk_create(bookings)


@login_required
def dashboard_view(request):
    today = timezone.now().date()
    tenant = request.user.tenant
    bookings_today = Booking.objects.filter(
        tenant=tenant, start_time__date=today,
    ).select_related('client', 'service', 'staff').order_by('start_time')
    upcoming = Booking.objects.filter(
        tenant=tenant, start_time__gte=timezone.now(),
        status__in=['pending', 'confirmed'],
    ).order_by('start_time')[:5]
    total = Booking.objects.filter(tenant=tenant).count()
    membership = getattr(tenant, 'membership', None)
    total_clients = Client.objects.filter(tenant=tenant).count()
    total_services = Service.objects.filter(tenant=tenant, is_active=True).count()
    return render(request, 'dashboard.html', {
        'bookings_today': bookings_today,
        'upcoming': upcoming,
        'total': total,
        'today_count': bookings_today.count(),
        'membership': membership,
        'total_clients': total_clients,
        'total_services': total_services,
    })


@login_required
def profile_view(request):
    tenant = request.user.tenant
    form = ProfileForm(request.POST or None, instance=tenant)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('dashboard')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def staff_list(request):
    staff = User.objects.filter(tenant=request.user.tenant).order_by('role', 'username')
    return render(request, 'accounts/staff/list.html', {'staff': staff})


@login_required
def staff_create(request):
    form = StaffForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.tenant = request.user.tenant
        user.role = 'staff'
        pwd = form.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)
        user.save()
        return redirect('staff_list')
    return render(request, 'accounts/staff/form.html', {'form': form, 'title': 'Agregar profesional'})


@login_required
def staff_edit(request, pk):
    member = get_object_or_404(User, pk=pk, tenant=request.user.tenant)
    form = StaffForm(request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        pwd = form.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)
        user.save()
        return redirect('staff_list')
    return render(request, 'accounts/staff/form.html', {'form': form, 'title': 'Editar profesional'})


@login_required
def staff_delete(request, pk):
    member = get_object_or_404(User, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST' and member != request.user:
        member.delete()
    return redirect('staff_list')
