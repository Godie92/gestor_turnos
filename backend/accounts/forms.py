from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User
from tenants.models import Tenant


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Usuario', 'class': 'form-input'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña', 'class': 'form-input'})
    )


class RegisterSalonForm(forms.Form):
    salon_name = forms.CharField(
        max_length=255,
        label='Nombre del salón',
        widget=forms.TextInput(attrs={'placeholder': 'Mi Salón', 'class': 'form-input'})
    )
    subdomain = forms.CharField(
        max_length=100,
        label='Subdominio',
        widget=forms.TextInput(attrs={'placeholder': 'mi-salon', 'class': 'form-input'})
    )
    username = forms.CharField(
        max_length=150,
        label='Usuario',
        widget=forms.TextInput(attrs={'placeholder': 'admin', 'class': 'form-input'})
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com', 'class': 'form-input'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'class': 'form-input'})
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'class': 'form-input'})
    )

    def clean_subdomain(self):
        subdomain = self.cleaned_data['subdomain'].lower().strip()
        if Tenant.objects.filter(subdomain=subdomain).exists():
            raise forms.ValidationError('Este subdominio ya está en uso.')
        return subdomain

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuario ya existe.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password2'):
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned_data
