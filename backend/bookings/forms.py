from django import forms
from .models import Booking


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['client_name', 'service', 'start_time', 'end_time']
        labels = {
            'client_name': 'Nombre del cliente',
            'service': 'Servicio',
            'start_time': 'Inicio',
            'end_time': 'Fin',
        }
        widgets = {
            'client_name': forms.TextInput(attrs={'placeholder': 'Nombre del cliente', 'class': 'form-input'}),
            'service': forms.TextInput(attrs={'placeholder': 'Corte, tinte, manicura...', 'class': 'form-input'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('La hora de fin debe ser posterior a la de inicio.')
        return cleaned_data
