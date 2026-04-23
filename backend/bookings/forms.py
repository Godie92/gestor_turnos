from django import forms
from .models import Booking, Service, Client


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'duration', 'color', 'is_active', 'order']
        labels = {
            'name': 'Nombre del servicio',
            'description': 'Descripción',
            'price': 'Precio ($)',
            'duration': 'Duración (minutos)',
            'color': 'Color en el calendario',
            'is_active': 'Activo',
            'order': 'Orden',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: Corte de cabello'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Opcional'}),
            'price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'duration': forms.NumberInput(attrs={'class': 'form-input'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-20 rounded cursor-pointer border border-gray-300'}),
            'order': forms.NumberInput(attrs={'class': 'form-input'}),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'phone', 'email', 'notes']
        labels = {
            'name': 'Nombre completo',
            'phone': 'Teléfono / WhatsApp',
            'email': 'Email',
            'notes': 'Notas internas',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nombre del cliente'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+54 9 11 1234-5678'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'correo@ejemplo.com'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Alergias, preferencias, etc.'}),
        }


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['client', 'client_name', 'service', 'service_name', 'staff', 'start_time', 'end_time', 'status', 'price', 'notes']
        labels = {
            'client': 'Cliente (de la lista)',
            'client_name': 'Nombre del cliente',
            'service': 'Servicio (del catálogo)',
            'service_name': 'Nombre del servicio',
            'staff': 'Profesional asignado',
            'start_time': 'Inicio',
            'end_time': 'Fin',
            'status': 'Estado',
            'price': 'Precio ($)',
            'notes': 'Notas',
        }
        widgets = {
            'client': forms.Select(attrs={'class': 'form-input'}),
            'client_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'O escribí el nombre directamente'}),
            'service': forms.Select(attrs={'class': 'form-input'}),
            'service_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'O escribí el servicio directamente'}),
            'staff': forms.Select(attrs={'class': 'form-input'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }

    def __init__(self, tenant=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['client'].queryset = Client.objects.filter(tenant=tenant)
            self.fields['client'].empty_label = '— Sin cliente registrado —'
            self.fields['service'].queryset = Service.objects.filter(tenant=tenant, is_active=True)
            self.fields['service'].empty_label = '— Sin servicio del catálogo —'
            from accounts.models import User
            self.fields['staff'].queryset = User.objects.filter(tenant=tenant, role__in=['owner', 'staff'])
            self.fields['staff'].empty_label = '— Sin asignar —'
        self.fields['client'].required = False
        self.fields['service'].required = False
        self.fields['staff'].required = False
        self.fields['price'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Auto-fill name from client if selected
        client = cleaned_data.get('client')
        if client and not cleaned_data.get('client_name'):
            cleaned_data['client_name'] = client.name
        # Auto-fill service name from service if selected
        service = cleaned_data.get('service')
        if service and not cleaned_data.get('service_name'):
            cleaned_data['service_name'] = service.name
        if not cleaned_data.get('client_name'):
            raise forms.ValidationError('Ingresá el nombre del cliente.')
        if not cleaned_data.get('service_name'):
            raise forms.ValidationError('Ingresá el nombre del servicio.')
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('La hora de fin debe ser posterior a la de inicio.')
        return cleaned_data
