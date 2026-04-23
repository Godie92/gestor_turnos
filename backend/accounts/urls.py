from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('demo/', views.demo_view, name='demo'),
]
