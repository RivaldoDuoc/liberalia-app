document.addEventListener('DOMContentLoaded', function () {
  const $  = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  // Referenciar a modales
  const modalEditarEl = document.getElementById('modalEditarEditorial');
  if (!modalEditarEl) {
    console.error('[editoriales_editar] No se encontró #modalEditarEditorial');
    return;
  }
  const modalEditar = (bootstrap?.Modal?.getOrCreateInstance)
    ? bootstrap.Modal.getOrCreateInstance(modalEditarEl)
    : new bootstrap.Modal(modalEditarEl);

  const modalConfirmEl = document.getElementById('modalConfirmarGuardarEditorial');
  const modalConfirm = modalConfirmEl
    ? ((bootstrap?.Modal?.getOrCreateInstance)
        ? bootstrap.Modal.getOrCreateInstance(modalConfirmEl)
        : new bootstrap.Modal(modalConfirmEl))
    : null;

  // Alertas del modal Editar
  const alertBox = document.getElementById('editarEditorialAlert');
  const hideAlert = () => alertBox && alertBox.classList.add('d-none');
  const showAlert = (kind, msg) => {
    if (!alertBox) return;
    alertBox.className = `alert alert-${kind}`;
    alertBox.textContent = msg;
    alertBox.classList.remove('d-none');
  };

  // Guardar quién abrió el modal
  let lastTriggerBtn = null;

  // Precargar datos al abrir --------
  modalEditarEl.addEventListener('show.bs.modal', (event) => {
    hideAlert();
    const button = event.relatedTarget; 
    lastTriggerBtn = button || null;

    if (button) {
      $('#ed-id').value       = button.dataset.editorialId || '';
      $('#ed-nombre').value   = button.dataset.nombre || '';
      $('#ed-idfiscal').value = button.dataset.idfiscal || '';
      $('#ed-cargo').value    = button.dataset.cargo || '';
      $('#ed-gastos').value   = button.dataset.gastos || '';
      $('#ed-fletes').value   = button.dataset.fletes || '';
      $('#ed-margen').value   = button.dataset.margen || '';
    }

    // Limpia errores previos
    modalEditarEl.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    modalEditarEl.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
  });

  // Al cerrar: quitar foco del botón "Editar" --------
  modalEditarEl.addEventListener('hidden.bs.modal', () => {
    if (lastTriggerBtn && typeof lastTriggerBtn.blur === 'function') {
      lastTriggerBtn.blur();
    }
    lastTriggerBtn = null;
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  });

  // Fallback: si fallara data-bs-toggle, abre al click 
  $$('.btn-editar').forEach(btn => {
    btn.addEventListener('click', () => {
      try { modalEditar.show(); } catch (e) { /* noop */ }
    });
  });

  //Guardado
  async function guardarEditorial() {
    hideAlert();

    const id = $('#ed-id').value;
    const payload = {
      nombre: $('#ed-nombre').value,
      id_fiscal: $('#ed-idfiscal').value,
      cargo_origen: $('#ed-cargo').value || null,
      gastos_indirectos: $('#ed-gastos').value || null,
      recargo_fletes: $('#ed-fletes').value || null,
      margen_comercializacion: $('#ed-margen').value || null,
    };

    // CSRF desde el form
    const csrfInput = document.querySelector('#formEditarEditorial input[name="csrfmiddlewaretoken"]');
    const csrf = csrfInput ? csrfInput.value : '';

    const pattern = window.EDITORIALES_EDIT_URL_PATTERN || '/roles/admin/editoriales/__ID__/editar/';
    const url = pattern.replace('__ID__', id);

    // Limpia marcas de error
    modalEditarEl.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    modalEditarEl.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

    try {
      const resp = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        const html = await resp.text();
        console.error('[editoriales_editar] Respuesta no JSON:', html);
        showAlert('danger', 'Respuesta no válida del servidor.');
        return;
      }

      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        if (data.errors) {
          Object.entries(data.errors).forEach(([field, msgs]) => {
            const fieldId = ({
              nombre: 'ed-nombre',
              id_fiscal: 'ed-idfiscal',
              cargo_origen: 'ed-cargo',
              gastos_indirectos: 'ed-gastos',
              recargo_fletes: 'ed-fletes',
              margen_comercializacion: 'ed-margen',
            })[field];
            if (fieldId) {
              const input = document.getElementById(fieldId);
              input.classList.add('is-invalid');
              const fb = modalEditarEl.querySelector(`.invalid-feedback[data-for="${field}"]`);
              if (fb) fb.textContent = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
            }
          });
          return;
        }
        showAlert('danger', data.error || 'No se pudo guardar la editorial.');
        return;
      }
     
      showAlert('success', 'Editorial actualizada correctamente.');
      if (modalConfirm) modalConfirm.hide();
      setTimeout(() => window.location.reload(), 800);

    } catch (e) {
      console.error('[editoriales_editar] Error:', e);
      showAlert('danger', `Error de red: ${e}`);
    }
  }

  // Botones: guardar/confirmación
  const btnGuardar = document.getElementById('btnGuardarEditorial');
  if (!btnGuardar) {
    console.error('[editoriales_editar] No se encontró #btnGuardarEditorial');
    return;
  }

  // Abrir modal de confirmación al pulsar Guardar
  btnGuardar.addEventListener('click', () => {
    hideAlert();
    if (modalConfirm) {
      modalConfirm.show();
    } else {      
      guardarEditorial();
    }
  });

  // Confirmar desde el modal de confirmación
  const btnConfirmar = document.getElementById('btnConfirmarGuardarEditorial');
  if (btnConfirmar) {
    btnConfirmar.addEventListener('click', () => {
      guardarEditorial();
    });
  }

  // Al cerrar confirmación, limpiar focos residuales
  if (modalConfirmEl) {
    modalConfirmEl.addEventListener('hidden.bs.modal', () => {
      if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
      }
    });
  }
});
