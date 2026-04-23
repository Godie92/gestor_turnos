import json
import datetime
import mercadopago
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import Tenant, Membership


@staff_member_required
def superadmin_panel(request):
    status_filter = request.GET.get('status', 'all')
    today = timezone.now().date()
    soon = today + datetime.timedelta(days=7)

    qs = Membership.objects.select_related('tenant').order_by('-created_at')
    if status_filter == 'active':
        qs = qs.filter(status=Membership.STATUS_ACTIVE)
    elif status_filter == 'unpaid':
        qs = qs.filter(status=Membership.STATUS_UNPAID)
    elif status_filter == 'expired':
        qs = qs.filter(status=Membership.STATUS_EXPIRED)
    elif status_filter == 'trial':
        qs = qs.filter(status=Membership.STATUS_TRIAL)
    elif status_filter == 'expiring':
        qs = qs.filter(status=Membership.STATUS_ACTIVE, end_date__lte=soon, end_date__gte=today)

    stats = {
        'total': Membership.objects.count(),
        'active': Membership.objects.filter(status=Membership.STATUS_ACTIVE).count(),
        'unpaid': Membership.objects.filter(status=Membership.STATUS_UNPAID).count(),
        'trial': Membership.objects.filter(status=Membership.STATUS_TRIAL).count(),
        'expired': Membership.objects.filter(status=Membership.STATUS_EXPIRED).count(),
        'expiring': Membership.objects.filter(
            status=Membership.STATUS_ACTIVE, end_date__lte=soon, end_date__gte=today
        ).count(),
    }

    return render(request, 'panel/dashboard.html', {
        'memberships': qs,
        'stats': stats,
        'status_filter': status_filter,
        'today': today,
    })


@staff_member_required
def membership_mark_paid(request, pk):
    membership = get_object_or_404(Membership, pk=pk)
    if request.method == 'POST':
        membership.status = Membership.STATUS_ACTIVE
        membership.start_date = datetime.date.today()
        if membership.plan == Membership.PLAN_YEARLY:
            membership.end_date = datetime.date.today() + datetime.timedelta(days=365)
        else:
            membership.end_date = datetime.date.today() + datetime.timedelta(days=30)
        membership.save()
    return redirect(reverse('superadmin_panel') + '?status=' + request.GET.get('back', 'all'))


@login_required
def payment_checkout(request):
    tenant = request.user.tenant
    membership = getattr(tenant, 'membership', None)
    if not membership:
        return redirect('dashboard')

    plan = request.GET.get('plan', 'monthly')
    amount = Membership.AMOUNT_YEARLY if plan == 'yearly' else Membership.AMOUNT_MONTHLY
    plan_label = 'Anual' if plan == 'yearly' else 'Mensual'

    if request.method == 'POST':
        try:
            sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
            preference_data = {
                "items": [{
                    "title": f"Salon Pro — Plan {plan_label}",
                    "quantity": 1,
                    "currency_id": "ARS",
                    "unit_price": float(amount),
                }],
                "payer": {"email": request.user.email or "cliente@salonpro.com"},
                "back_urls": {
                    "success": request.build_absolute_uri(reverse('payment_success')),
                    "failure": request.build_absolute_uri(reverse('payment_failure')),
                    "pending": request.build_absolute_uri(reverse('payment_failure')),
                },
                "auto_return": "approved",
                "external_reference": f"{tenant.id}|{plan}",
                "notification_url": request.build_absolute_uri(reverse('payment_webhook')),
            }
            result = sdk.preference().create(preference_data)
            preference = result["response"]
            membership.mp_preference_id = preference["id"]
            membership.save(update_fields=['mp_preference_id'])

            if settings.MP_USE_SANDBOX:
                return redirect(preference["sandbox_init_point"])
            return redirect(preference["init_point"])
        except Exception as e:
            return render(request, 'payment/checkout.html', {
                'membership': membership,
                'plan': plan,
                'amount': amount,
                'plan_label': plan_label,
                'error': str(e),
            })

    return render(request, 'payment/checkout.html', {
        'membership': membership,
        'plan': plan,
        'amount': amount,
        'plan_label': plan_label,
    })


@login_required
def payment_success(request):
    tenant = request.user.tenant
    membership = getattr(tenant, 'membership', None)
    payment_id = request.GET.get('payment_id', '')
    if membership and payment_id:
        membership.status = Membership.STATUS_ACTIVE
        membership.mp_payment_id = payment_id
        membership.start_date = datetime.date.today()
        external_ref = request.GET.get('external_reference', '')
        plan = external_ref.split('|')[1] if '|' in external_ref else 'monthly'
        if plan == 'yearly':
            membership.plan = Membership.PLAN_YEARLY
            membership.end_date = datetime.date.today() + datetime.timedelta(days=365)
            membership.amount = Membership.AMOUNT_YEARLY
        else:
            membership.plan = Membership.PLAN_MONTHLY
            membership.end_date = datetime.date.today() + datetime.timedelta(days=30)
            membership.amount = Membership.AMOUNT_MONTHLY
        membership.save()
    return render(request, 'payment/success.html', {'membership': membership})


@login_required
def payment_failure(request):
    return render(request, 'payment/failure.html')


@csrf_exempt
def payment_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=200)
    try:
        data = json.loads(request.body)
        if data.get('type') != 'payment':
            return HttpResponse(status=200)
        payment_id = data['data']['id']
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        payment_info = sdk.payment().get(payment_id)
        payment = payment_info['response']

        if payment.get('status') != 'approved':
            return HttpResponse(status=200)

        external_ref = payment.get('external_reference', '')
        if '|' not in external_ref:
            return HttpResponse(status=200)

        tenant_id, plan = external_ref.split('|', 1)
        membership = Membership.objects.select_related('tenant').get(tenant_id=tenant_id)
        membership.status = Membership.STATUS_ACTIVE
        membership.mp_payment_id = str(payment_id)
        membership.start_date = datetime.date.today()
        if plan == 'yearly':
            membership.plan = Membership.PLAN_YEARLY
            membership.end_date = datetime.date.today() + datetime.timedelta(days=365)
            membership.amount = Membership.AMOUNT_YEARLY
        else:
            membership.plan = Membership.PLAN_MONTHLY
            membership.end_date = datetime.date.today() + datetime.timedelta(days=30)
            membership.amount = Membership.AMOUNT_MONTHLY
        membership.save()
    except Exception:
        pass
    return HttpResponse(status=200)
