/* Polling para la pantalla TV */
(function () {
  const slug = document.getElementById('tv-root').dataset.slug;
  const $ = id => document.getElementById(id);

  function pad(n) { return String(n).padStart(2, '0'); }

  function updateClock() {
    const now = new Date();
    $('tv-clock').textContent =
      `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  }

  function refresh() {
    fetch(`/api/v1/${slug}/queue`)
      .then(r => r.json())
      .then(data => {
        // En atención
        const cur = data.current;
        $('current-name').textContent    = cur ? cur.client_name : '—';
        $('current-service').textContent = cur ? (cur.service_name || '') : '';

        // Próximo
        const nxt = data.called || data.next;
        $('next-name').textContent    = nxt ? nxt.client_name : '—';
        $('next-service').textContent = nxt ? (nxt.service_name || '') : '';

        // En espera + tiempo estimado
        $('waiting-count').textContent = data.waiting_count;
        const waitEst = $('tv-wait-est');
        if (waitEst) {
          const total = data.waiting_count * (data.avg_service_min || 15);
          waitEst.textContent = total > 0 ? `~${total} min` : '—';
        }
      })
      .catch(() => {}); // silenciar errores de red
  }

  updateClock();
  setInterval(updateClock, 1000);
  refresh();
  setInterval(refresh, 4000);
})();
