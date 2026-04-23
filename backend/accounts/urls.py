from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('demo/', views.demo_view, name='demo'),
    path('perfil/', views.profile_view, name='profile'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/nuevo/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/editar/', views.staff_edit, name='staff_edit'),
    path('staff/<int:pk>/eliminar/', views.staff_delete, name='staff_delete'),
]
