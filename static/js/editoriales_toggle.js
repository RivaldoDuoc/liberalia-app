document.addEventListener('DOMContentLoaded', function () {
  const $  = (s) => document.querySelector(s);

  const modalEl = document.getElementById('modalConfirmToggleEditorial');
  if (!modalEl) return;

  const modal = (bootstrap?.Modal?.getOrCreateInstance)
    ? bootstrap.Modal.getOrCreateInstance(modalEl)
    : new bootstrap.Modal(modalEl);

  const titleEl = document.getElementById('modalConfirmToggleEditorialTitle');
  const msgEl   = document.getElementById('modalConfirmToggleEditorialMsg');
  const btnOk   = document.getElementById('btnConfirmarToggleEditorial');

  // Estado de la acción actual
  let currentId     = null;
  let currentName   = '';
  let setActiveTo   = null; // true = habilitar, false = deshabilitar
  let triggerBtnRef = null;

  // Fallback CSRF si no hay input en el DOM
  function getCookie (name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
  }

  // Al ABRIR el modal por Bootstrap: rellenar título y pregunta
  modalEl.addEventListener('show.bs.modal', (ev) => {
    const btn = ev.relatedTarget; 
    triggerBtnRef = btn || null;

    const id     = btn?.dataset?.editorialId;
    const nombre = btn?.dataset?.nombre || '';
    const activo = (btn?.dataset?.activo === '1');

    currentId   = id || null;
    currentName = nombre;
    setActiveTo = !activo;

    // Título y pregunta para confirmar
    titleEl.textContent = setActiveTo ? 'Habilitar editorial' : 'Deshabilitar editorial';
    msgEl.textContent   = setActiveTo
      ? `¿Seguro que desea habilitar la editorial “${nombre}”?`
      : `¿Seguro que desea deshabilitar la editorial “${nombre}”?`;

    // Cambiar texto del botón según acción
    btnOk.textContent = setActiveTo ? 'Habilitar' : 'Deshabilitar';
  });

  // Al CERRAR el modal: quitar foco del botón que lo abrió (para que no quede "encendido")
  modalEl.addEventListener('hidden.bs.modal', () => {
    if (triggerBtnRef && typeof triggerBtnRef.blur === 'function') triggerBtnRef.blur();
    triggerBtnRef = null;
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  });

  // Confirmar la acción / POST al endpoint
  btnOk.addEventListener('click', async () => {
    if (!currentId) return;

    btnOk.disabled = true;

    // CSRF: intenta tomarlo de cualquier input; si no hay, usa cookie
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const csrf = csrfInput ? csrfInput.value : (getCookie('csrftoken') || '');

    const url = (window.EDITORIALES_TOGGLE_URL_PATTERN || '/roles/admin/editoriales/__ID__/toggle/')
                  .replace('__ID__', currentId);

    try {
      const resp = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ activo: setActiveTo })
      });

      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        console.error('[editoriales_toggle] Respuesta no JSON:', await resp.text());
        btnOk.disabled = false;
        return;
      }

      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        console.error('[editoriales_toggle] Error al alternar estado:', data);
        btnOk.disabled = false;
        return;
      }

      modal.hide();
      setTimeout(() => window.location.reload(), 150);

    } catch (e) {
      console.error('[editoriales_toggle] Error de red:', e);
      btnOk.disabled = false;
    }
  });

  // Fallback por si algún botón no tiene data-bs-toggle (abrir modal manualmente)
  document.querySelectorAll('.btn-toggle-estado').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!btn.getAttribute('data-bs-toggle')) {
        const id     = btn.dataset.editorialId;
        const nombre = btn.dataset.nombre || '';
        const activo = (btn.dataset.activo === '1');

        currentId   = id;
        currentName = nombre;
        setActiveTo = !activo;

        titleEl.textContent = setActiveTo ? 'Habilitar editorial' : 'Deshabilitar editorial';
        msgEl.textContent   = setActiveTo
          ? `¿Seguro que desea habilitar la editorial “${nombre}”?`
          : `¿Seguro que desea deshabilitar la editorial “${nombre}”?`;

        btnOk.textContent = setActiveTo ? 'Habilitar' : 'Deshabilitar';
        triggerBtnRef = btn;
        modal.show();
      }
    });
  });
});
