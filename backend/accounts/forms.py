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
        max_length=255, label='Nombre del negocio',
        widget=forms.TextInput(attrs={'placeholder': 'Mi Negocio', 'class': 'form-input'})
    )
    subdomain = forms.CharField(
        max_length=100, label='Subdominio',
        widget=forms.TextInput(attrs={'placeholder': 'mi-negocio', 'class': 'form-input'})
    )
    username = forms.CharField(
        max_length=150, label='Usuario',
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


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['name', 'color']
        labels = {'name': 'Nombre del negocio', 'color': 'Color principal'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-20 rounded cursor-pointer border border-gray-300'}),
        }


class StaffForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••'}),
        required=False,
        help_text='Dejá en blanco para no cambiar.'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Email',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Este usuario ya existe.')
        return username
