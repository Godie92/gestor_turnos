import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from .models import Booking, Service, Client
from .forms import BookingForm, ServiceForm, ClientForm
from .emails import send_booking_confirmation

CALENDAR_START = 8
CALENDAR_END = 21
CALENDAR_HOURS = CALENDAR_END - CALENDAR_START


# ── BOOKINGS ─────────────────────────────────────────────────

@login_required
def booking_list(request):
    status = request.GET.get('status', '')
    qs = Booking.objects.filter(tenant=request.user.tenant).select_related('client', 'service', 'staff')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'bookings/list.html', {
        'bookings': qs,
        'status_filter': status,
        'status_choices': Booking.STATUS_CHOICES,
    })


@login_required
def booking_create(request):
    form = BookingForm(tenant=request.user.tenant, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.tenant = request.user.tenant
        booking.save()
        send_booking_confirmation(booking)
        return redirect('booking_list')
    return render(request, 'bookings/form.html', {'form': form, 'title': 'Nueva reserva'})


@login_required
def booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user.tenant)
    form = BookingForm(tenant=request.user.tenant, data=request.POST or None, instance=booking)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('booking_list')
    return render(request, 'bookings/form.html', {'form': form, 'title': 'Editar reserva', 'booking': booking})


@login_required
def booking_delete(request, pk):
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST':
        booking.delete()
        return redirect('booking_list')
    return render(request, 'bookings/confirm_delete.html', {'booking': booking})


@login_required
def booking_status(request, pk):
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Booking.STATUS_CHOICES):
            booking.status = new_status
            booking.save(update_fields=['status'])
    return redirect(request.POST.get('next', 'booking_list'))


# ── CALENDAR ─────────────────────────────────────────────────

@login_required
def calendar_view(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    today = timezone.now().date()
    week_offset = int(request.GET.get('week', 0))
    week_start = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(weeks=week_offset)
    days = [week_start + datetime.timedelta(days=i) for i in range(7)]

    staff_filter = request.GET.get('staff', '')
    service_filter = request.GET.get('service', '')

    qs = Booking.objects.filter(
        tenant=request.user.tenant,
        start_time__date__gte=days[0],
        start_time__date__lte=days[-1],
    ).select_related('client', 'service', 'staff')

    if staff_filter:
        qs = qs.filter(staff_id=staff_filter)
    if service_filter:
        qs = qs.filter(service_id=service_filter)

    bookings = list(qs)

    total_minutes = CALENDAR_HOURS * 60
    for b in bookings:
        local_start = timezone.localtime(b.start_time)
        local_end = timezone.localtime(b.end_time)
        start_min = (local_start.hour - CALENDAR_START) * 60 + local_start.minute
        end_min = (local_end.hour - CALENDAR_START) * 60 + local_end.minute
        b.top_pct = max(0, round(start_min / total_minutes * 100, 2))
        b.height_pct = max(3, round((end_min - start_min) / total_minutes * 100, 2))
        b.cal_day = local_start.date()

    bookings_by_day = {day: [b for b in bookings if b.cal_day == day] for day in days}

    staff_list = User.objects.filter(tenant=request.user.tenant).exclude(is_superuser=True)
    services = Service.objects.filter(tenant=request.user.tenant, is_active=True)

    # Build query string to preserve filters when navigating weeks
    filter_qs = ''
    if staff_filter:
        filter_qs += f'&staff={staff_filter}'
    if service_filter:
        filter_qs += f'&service={service_filter}'

    return render(request, 'bookings/calendar.html', {
        'days': days,
        'bookings_by_day': bookings_by_day,
        'today': today,
        'week_offset': week_offset,
        'hours': range(CALENDAR_START, CALENDAR_END),
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1,
        'staff_list': staff_list,
        'services': services,
        'staff_filter': staff_filter,
        'service_filter': service_filter,
        'filter_qs': filter_qs,
    })


# ── STATS ─────────────────────────────────────────────────────

@login_required
def stats_view(request):
    tenant = request.user.tenant
    today = timezone.now().date()
    month_start = today.replace(day=1)

    total = Booking.objects.filter(tenant=tenant).count()
    this_month = Booking.objects.filter(tenant=tenant, start_time__date__gte=month_start).count()
    completed = Booking.objects.filter(tenant=tenant, status='completed').count()
    revenue = Booking.objects.filter(
        tenant=tenant, status='completed', price__isnull=False
    ).aggregate(total=Sum('price'))['total'] or 0

    # By status
    by_status = {s: Booking.objects.filter(tenant=tenant, status=s).count() for s, _ in Booking.STATUS_CHOICES}

    # Top services
    top_services = (
        Booking.objects.filter(tenant=tenant)
        .values('service_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )
    max_svc = top_services[0]['count'] if top_services else 1

    # By weekday
    day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    by_weekday = []
    for i, name in enumerate(day_names):
        count = Booking.objects.filter(tenant=tenant, start_time__week_day=(i + 2) % 7 + 1).count()
        by_weekday.append({'name': name, 'count': count})
    max_day = max((d['count'] for d in by_weekday), default=1) or 1

    # Last 6 months revenue
    monthly = []
    for i in range(5, -1, -1):
        d = today - datetime.timedelta(days=i * 30)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year + 1, month=1, day=1)
        else:
            m_end = d.replace(month=d.month + 1, day=1)
        rev = Booking.objects.filter(
            tenant=tenant, status='completed',
            start_time__date__gte=m_start, start_time__date__lt=m_end,
            price__isnull=False,
        ).aggregate(t=Sum('price'))['t'] or 0
        monthly.append({'label': m_start.strftime('%b'), 'value': float(rev)})
    max_monthly = max((m['value'] for m in monthly), default=1) or 1

    # Top clients
    top_clients = (
        Booking.objects.filter(tenant=tenant)
        .values('client_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    return render(request, 'bookings/stats.html', {
        'total': total,
        'this_month': this_month,
        'completed': completed,
        'revenue': revenue,
        'by_status': by_status,
        'top_services': top_services,
        'max_svc': max_svc,
        'by_weekday': by_weekday,
        'max_day': max_day,
        'monthly': monthly,
        'max_monthly': max_monthly,
        'top_clients': top_clients,
    })


# ── SERVICES ─────────────────────────────────────────────────

@login_required
def service_list(request):
    services = Service.objects.filter(tenant=request.user.tenant)
    return render(request, 'bookings/services/list.html', {'services': services})


@login_required
def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        svc = form.save(commit=False)
        svc.tenant = request.user.tenant
        svc.save()
        return redirect('service_list')
    return render(request, 'bookings/services/form.html', {'form': form, 'title': 'Nuevo servicio'})


@login_required
def service_edit(request, pk):
    svc = get_object_or_404(Service, pk=pk, tenant=request.user.tenant)
    form = ServiceForm(request.POST or None, instance=svc)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('service_list')
    return render(request, 'bookings/services/form.html', {'form': form, 'title': 'Editar servicio'})


@login_required
def service_delete(request, pk):
    svc = get_object_or_404(Service, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST':
        svc.delete()
    return redirect('service_list')


# ── CLIENTS ──────────────────────────────────────────────────

@login_required
def client_list(request):
    q = request.GET.get('q', '')
    clients = Client.objects.filter(tenant=request.user.tenant)
    if q:
        clients = clients.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return render(request, 'bookings/clients/list.html', {'clients': clients, 'q': q})


@login_required
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        client = form.save(commit=False)
        client.tenant = request.user.tenant
        client.save()
        return redirect('client_list')
    return render(request, 'bookings/clients/form.html', {'form': form, 'title': 'Nuevo cliente'})


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk, tenant=request.user.tenant)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('client_detail', pk=pk)
    return render(request, 'bookings/clients/form.html', {'form': form, 'title': 'Editar cliente', 'client': client})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk, tenant=request.user.tenant)
    bookings = client.bookings.all()
    return render(request, 'bookings/clients/detail.html', {'client': client, 'bookings': bookings})


@login_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST':
        client.delete()
        return redirect('client_list')
    return render(request, 'bookings/clients/confirm_delete.html', {'client': client})
