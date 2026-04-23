from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Booking
from .forms import BookingForm


@login_required
def booking_list(request):
    bookings = Booking.objects.filter(
        tenant=request.user.tenant
    ).order_by('-start_time')
    return render(request, 'bookings/list.html', {'bookings': bookings})


@login_required
def booking_create(request):
    form = BookingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.tenant = request.user.tenant
        booking.save()
        return redirect('booking_list')
    return render(request, 'bookings/form.html', {'form': form, 'title': 'Nueva Reserva'})


@login_required
def booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user.tenant)
    form = BookingForm(request.POST or None, instance=booking)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('booking_list')
    return render(request, 'bookings/form.html', {'form': form, 'title': 'Editar Reserva'})


@login_required
def booking_delete(request, pk):
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user.tenant)
    if request.method == 'POST':
        booking.delete()
        return redirect('booking_list')
    return render(request, 'bookings/confirm_delete.html', {'booking': booking})
