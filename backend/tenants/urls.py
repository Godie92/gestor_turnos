from django.urls import path
from . import views

urlpatterns = [
    path('panel/', views.superadmin_panel, name='superadmin_panel'),
    path('panel/membresia/<int:pk>/pagar/', views.membership_mark_paid, name='membership_mark_paid'),
    path('pagar/', views.payment_checkout, name='payment_checkout'),
    path('pagar/exito/', views.payment_success, name='payment_success'),
    path('pagar/error/', views.payment_failure, name='payment_failure'),
    path('pagar/webhook/', views.payment_webhook, name='payment_webhook'),
]
