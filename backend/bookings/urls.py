from django.urls import path
from . import views

urlpatterns = [
    # Bookings
    path('', views.booking_list, name='booking_list'),
    path('nueva/', views.booking_create, name='booking_create'),
    path('<int:pk>/editar/', views.booking_edit, name='booking_edit'),
    path('<int:pk>/eliminar/', views.booking_delete, name='booking_delete'),
    path('<int:pk>/estado/', views.booking_status, name='booking_status'),

    # Calendar & Stats
    path('calendario/', views.calendar_view, name='calendar'),
    path('estadisticas/', views.stats_view, name='stats'),

    # Services
    path('servicios/', views.service_list, name='service_list'),
    path('servicios/nuevo/', views.service_create, name='service_create'),
    path('servicios/<int:pk>/editar/', views.service_edit, name='service_edit'),
    path('servicios/<int:pk>/eliminar/', views.service_delete, name='service_delete'),

    # Clients
    path('clientes/', views.client_list, name='client_list'),
    path('clientes/nuevo/', views.client_create, name='client_create'),
    path('clientes/<int:pk>/', views.client_detail, name='client_detail'),
    path('clientes/<int:pk>/editar/', views.client_edit, name='client_edit'),
    path('clientes/<int:pk>/eliminar/', views.client_delete, name='client_delete'),
]
