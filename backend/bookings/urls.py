from django.urls import path
from . import views

urlpatterns = [
    path('', views.booking_list, name='booking_list'),
    path('nueva/', views.booking_create, name='booking_create'),
    path('<int:pk>/editar/', views.booking_edit, name='booking_edit'),
    path('<int:pk>/eliminar/', views.booking_delete, name='booking_delete'),
]
