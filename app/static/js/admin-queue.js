/* Panel admin — acciones de cola con AJAX + auto-refresh completo */
(function () {
  const slug = document.getElementById('queue-panel')?.dataset.slug;
  if (!slug) return;

  const csrfToken = document.querySelector('meta[name=csrf-token]')?.content || '';

  function postAction(url) {
    fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken,
      },
    })
      .then(r => r.json())
      .then(data => { if (data.ok) refreshQueue(); })
      .catch(() => refreshQueue());
  }

  // Delegación de eventos para botones de acción
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const entryId = btn.dataset.id;

    const urls = {
      llamar:    `/${slug}/admin/cola/${entryId}/llamar`,
      iniciar:   `/${slug}/admin/cola/${entryId}/iniciar`,
      finalizar: `/${slug}/admin/cola/${entryId}/finalizar`,
      cancelar:  `/${slug}/admin/cola/${entryId}/cancelar`,
    };

    if (urls[action]) {
      postAction(urls[action]);
    }
  });

  function badgeClass(status) {
    return `badge badge-${status}`;
  }

  function renderEntry(e) {
    let actions = '';
    if (e.status === 'waiting') {
      actions = `
        <button class="btn btn-info btn-sm" data-action="llamar" data-id="${e.id}">📢 Llamar</button>
        <button class="btn btn-danger btn-sm" data-action="cancelar" data-id="${e.id}">✕</button>`;
    } else if (e.status === 'called') {
      actions = `
        <button class="btn btn-success btn-sm" data-action="iniciar" data-id="${e.id}">▶ Iniciar</button>
        <button class="btn btn-danger btn-sm" data-action="cancelar" data-id="${e.id}">✕</button>`;
    } else if (e.status === 'in_service') {
      actions = `
        <button class="btn btn-success btn-sm" data-action="finalizar" data-id="${e.id}">✓ Listo</button>`;
    }

    const extraClass = e.status === 'in_service' ? 'is-in-service' : (e.status === 'called' ? 'is-called' : '');
    const waitLabel = (e.status === 'waiting' && e.est_wait_min > 0)
      ? `· ⏱ ~${e.est_wait_min} min` : '';
    const meta = [
      e.service_name || '—',
      e.client_phone ? `· ${e.client_phone}` : '',
      e.professional_name ? `· ${e.professional_name}` : '',
      waitLabel,
      `· <span class="${badgeClass(e.status)}">${e.status_label}</span>`,
    ].filter(Boolean).join(' ');

    return `
      <div class="queue-item ${extraClass}">
        <div class="queue-pos">${e.position}</div>
        <div class="queue-info">
          <div class="name">${e.client_name}</div>
          <div class="meta">${meta}</div>
        </div>
        <div class="queue-actions">${actions}</div>
      </div>`;
  }

  function refreshQueue() {
    fetch(`/api/v1/${slug}/queue`)
      .then(r => r.json())
      .then(data => {
        // Contador y promedio
        const counter = document.getElementById('waiting-count');
        if (counter) counter.textContent = data.waiting_count;
        const avgEl = document.getElementById('avg-min');
        if (avgEl) avgEl.textContent = data.avg_service_min;

        // En atención (panel superior)
        const inServiceEl = document.getElementById('in-service-name');
        if (inServiceEl) {
          inServiceEl.textContent = data.current ? data.current.client_name : 'Sin atención activa';
        }

        // Lista de cola completa
        const panel = document.getElementById('queue-panel');
        if (!panel) return;

        const all = [];
        if (data.current) all.push(data.current);
        if (data.called && (!data.current || data.called.id !== data.current.id)) all.push(data.called);
        data.waiting_list.forEach(e => {
          if (!all.find(x => x.id === e.id)) all.push(e);
        });

        if (all.length === 0) {
          panel.innerHTML = '<div class="empty-queue">🎉 La cola está vacía</div>';
        } else {
          panel.innerHTML = all.map(renderEntry).join('');
        }
      })
      .catch(() => {});
  }

  // Primer refresh inmediato + luego cada 8 segundos
  refreshQueue();
  setInterval(refreshQueue, 8000);
})();
