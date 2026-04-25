/* Formulario de reserva — carga dinámica de horarios */
(function () {
  const slug = document.getElementById('booking-form').dataset.slug;
  const serviceEl = document.getElementById('service_id');
  const professionalEl = document.getElementById('professional_id');
  const dateEl = document.getElementById('date');
  const slotsContainer = document.getElementById('slots-container');
  const timeInput = document.getElementById('time');
  const submitBtn = document.getElementById('submit-btn');

  function loadSlots() {
    const serviceId = serviceEl.value;
    const date = dateEl.value;
    if (!serviceId || !date) {
      slotsContainer.innerHTML = '';
      return;
    }

    const professionalId = professionalEl ? professionalEl.value : '';
    let url = `/api/v1/${slug}/slots?service_id=${serviceId}&date=${date}`;
    if (professionalId) url += `&professional_id=${professionalId}`;

    slotsContainer.innerHTML = '<p class="loading">Cargando horarios...</p>';
    timeInput.value = '';
    submitBtn.disabled = true;

    fetch(url)
      .then(r => r.json())
      .then(data => {
        if (!data.slots || data.slots.length === 0) {
          slotsContainer.innerHTML = '<p class="no-slots">Sin horarios disponibles para esta fecha.</p>';
          return;
        }

        slotsContainer.innerHTML = data.slots.map(slot =>
          `<button type="button" class="slot-btn" data-time="${slot.time}" data-iso="${slot.iso}">
            ${slot.time}
          </button>`
        ).join('');

        slotsContainer.querySelectorAll('.slot-btn').forEach(btn => {
          btn.addEventListener('click', () => {
            slotsContainer.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            timeInput.value = btn.dataset.time;
            submitBtn.disabled = false;
          });
        });
      })
      .catch(() => {
        slotsContainer.innerHTML = '<p class="no-slots">Error al cargar horarios.</p>';
      });
  }

  // Fecha mínima = hoy
  const today = new Date().toISOString().split('T')[0];
  dateEl.setAttribute('min', today);

  serviceEl.addEventListener('change', loadSlots);
  dateEl.addEventListener('change', loadSlots);
  if (professionalEl) professionalEl.addEventListener('change', loadSlots);
})();
