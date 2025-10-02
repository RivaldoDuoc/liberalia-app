document.addEventListener('DOMContentLoaded', function () {
  const $  = (s) => document.querySelector(s);

  const modalEl = document.getElementById('modalCrearEditorial');
  if (!modalEl) return;

  const modal = bootstrap?.Modal?.getOrCreateInstance
    ? bootstrap.Modal.getOrCreateInstance(modalEl)
    : new bootstrap.Modal(modalEl);

  const modalConfirmEl = document.getElementById('modalConfirmarCrearEditorial');
  const modalConfirm = modalConfirmEl
    ? (bootstrap?.Modal?.getOrCreateInstance
        ? bootstrap.Modal.getOrCreateInstance(modalConfirmEl)
        : new bootstrap.Modal(modalConfirmEl))
    : null;

  const alertBox = document.getElementById('crearEditorialAlert');
  const hideAlert = () => alertBox && alertBox.classList.add('d-none');
  const showAlert = (kind, msg) => {
    if (!alertBox) return;
    alertBox.className = `alert alert-${kind}`;
    alertBox.textContent = msg;
    alertBox.classList.remove('d-none');
  };

  // Limpia el formulario cada vez que se abre
  modalEl.addEventListener('show.bs.modal', () => {
    hideAlert();
    ['cr-nombre','cr-idfiscal','cr-cargo','cr-gastos','cr-fletes','cr-margen']
      .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    modalEl.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    modalEl.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
  });

  // Valida requeridos en cliente: si falla, NO abre confirmación
  function validarRequeridosYMarcar() {
    const payload = {
      nombre: ($('#cr-nombre')?.value || '').trim(),
      id_fiscal: ($('#cr-idfiscal')?.value || '').trim(),
      cargo_origen: $('#cr-cargo')?.value || '',
      gastos_indirectos: $('#cr-gastos')?.value || '',
      recargo_fletes: $('#cr-fletes')?.value || '',
      margen_comercializacion: $('#cr-margen')?.value || '',
    };

    let invalid = false;
    modalEl.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    modalEl.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

    const map = {
      nombre: 'cr-nombre',
      id_fiscal: 'cr-idfiscal',
      cargo_origen: 'cr-cargo',
      gastos_indirectos: 'cr-gastos',
      recargo_fletes: 'cr-fletes',
      margen_comercializacion: 'cr-margen',
    };

    // Requeridos vacíos
    Object.entries(payload).forEach(([k, v]) => {
      if (k !== 'id_fiscal' && !String(v).trim()) {
        invalid = true;
        const input = document.getElementById(map[k]);
        if (input) {
          input.classList.add('is-invalid');
          const fb = modalEl.querySelector(`.invalid-feedback[data-for="${k}"]`);
          if (fb) fb.textContent = 'Este campo es obligatorio';
        }
      }
    });

    // Rangos numéricos 0..100 en los % (solo si no estaban vacíos)
    ['cargo_origen','gastos_indirectos','recargo_fletes','margen_comercializacion'].forEach(k => {
      const v = payload[k];
      if (String(v).trim()) {
        const n = Number(v);
        if (Number.isNaN(n) || n < 0 || n > 100) {
          invalid = true;
          const input = document.getElementById(map[k]);
          if (input) {
            input.classList.add('is-invalid');
            const fb = modalEl.querySelector(`.invalid-feedback[data-for="${k}"]`);
            if (fb) fb.textContent = 'Debe ser un número entre 0 y 100';
          }
        }
      }
    });

    // foco en el primer inválido
    if (invalid) {
      const first = modalEl.querySelector('.is-invalid');
      if (first) first.focus();
    }

    return { invalid, payload };
  }

  // Botón "Guardar" -> validar campos; si ok, recién mostrar confirmación
  const btnCrear = document.getElementById('btnCrearEditorial');
  btnCrear?.addEventListener('click', () => {
    hideAlert();
    const { invalid, payload } = validarRequeridosYMarcar();
    if (invalid) return; // NO abrir confirmación

    // pequeño resumen para confirmación
    const resumen = document.getElementById('cr-resumen-nombre');
    if (resumen) resumen.textContent = payload.nombre || '(sin nombre)';

    if (modalConfirm) modalConfirm.show(); else doCreate(payload);
  });

  // Confirmar creación definitiva
  const btnConfirmar = document.getElementById('btnConfirmarCrearEditorial');
  btnConfirmar?.addEventListener('click', () => {
    const { invalid, payload } = validarRequeridosYMarcar();
    if (invalid) return;
    doCreate(payload);
  });

  async function doCreate(payload) {
    const csrf = document.querySelector('#formCrearEditorial input[name="csrfmiddlewaretoken"]')?.value || '';
    const url = window.EDITORIALES_CREATE_URL;

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
        console.error('[crear editorial] Respuesta no JSON:', html);
        showAlert('danger', 'Respuesta no válida del servidor.');
        return;
      }

      const data = await resp.json();

      if (!resp.ok || !data.ok) {
        if (data.errors) {
          // errores del servidor por campo
          Object.entries(data.errors).forEach(([field, msgs]) => {
            const fieldId = ({
              nombre: 'cr-nombre',
              id_fiscal: 'cr-idfiscal',
              cargo_origen: 'cr-cargo',
              gastos_indirectos: 'cr-gastos',
              recargo_fletes: 'cr-fletes',
              margen_comercializacion: 'cr-margen',
            })[field];
            if (fieldId) {
              const input = document.getElementById(fieldId);
              input?.classList.add('is-invalid');
              const fb = modalEl.querySelector(`.invalid-feedback[data-for="${field}"]`);
              if (fb) fb.textContent = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
            }
          });
          return;
        }
        showAlert('danger', data.error || 'No se pudo crear la editorial.');
        return;
      }

      // OK
      if (modalConfirm) modalConfirm.hide();
      showAlert('success', 'Editorial creada correctamente.');
      setTimeout(() => window.location.reload(), 700);

    } catch (e) {
      console.error('[crear editorial] Error:', e);
      showAlert('danger', `Error de red: ${e}`);
    }
  }
});


