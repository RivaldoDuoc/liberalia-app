//JS DEL MODAL PARA INVITAR USUARIOS AL SISTEMA

// Helpers para seleccionar elementos más fácilmente
document.addEventListener('DOMContentLoaded', function () {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  // Inicializo el modal principal de invitación
  const modalEl = $('#modalInvitarUsuario');
  if (!modalEl) return;

  const modalInvitar = new bootstrap.Modal(modalEl);
  const alertBox = $('#invitarAlert');

  function showAlert(kind, msg) {
    if (!alertBox) return;
    alertBox.className = `alert alert-${kind}`;
    alertBox.textContent = msg;
    alertBox.classList.remove('d-none');
  }
  function hideAlert() { if (alertBox) alertBox.classList.add('d-none'); }

  // Abrir modal al click del botón principal
  const btnAbrir = $('#btn-invitar');
  if (btnAbrir) {
    btnAbrir.addEventListener('click', () => {
      hideAlert();
      // Limpiar campos
      $('#formInvitarUsuario').reset?.();
      // Asegurar estado inicial (rol=CONSULTOR => oculta editoriales)
      $('#invRol').value = 'CONSULTOR';
      $('#invGrupoEditoriales').classList.add('d-none');
      modalInvitar.show();
    });
  }

  // Mostrar/ocultar editoriales según rol
  const selRol = $('#invRol');
  if (selRol) {
    selRol.addEventListener('change', (e) => {
      const esEditor = e.target.value === 'EDITOR';
      const grp = $('#invGrupoEditoriales');
      grp.classList.toggle('d-none', !esEditor);
    });
  }

  // Confirmación con modal compacto
  function confirmarInvitarModal(mensaje) {
    return new Promise((resolve) => {
      const el = document.getElementById('modalConfirmInvitar');
      const msg = document.getElementById('confirmInvitarMensaje');
      const btn = document.getElementById('btnConfirmInvitar');
      if (!el || !msg || !btn) { resolve(false); return; }

      msg.textContent = mensaje;

      const modal = new bootstrap.Modal(el, { backdrop: 'static', keyboard: false });

      const onClick = () => { modal.hide(); cleanup(); resolve(true); };
      const onHide = () => { cleanup(); resolve(false); };

      function cleanup() {
        btn.removeEventListener('click', onClick);
        el.removeEventListener('hidden.bs.modal', onHide);
      }

      btn.addEventListener('click', onClick, { once: true });
      el.addEventListener('hidden.bs.modal', onHide, { once: true });

      modal.show();
    });
  }

  // Enviar invitación
  const btnEnviar = $('#btnInvitarEnviar');
  if (btnEnviar) {
    btnEnviar.addEventListener('click', async () => {
      hideAlert();

      const nombre = ($('#invNombre').value || '').trim();
      const apellido = ($('#invApellido').value || '').trim();
      const correo = ($('#invCorreo').value || '').trim();
      const rol = $('#invRol').value;
      const idFiscal = ($('#invIdFiscal').value || '').trim();

      // Validación mínima
      if (!nombre || !apellido || !correo) {
        showAlert('warning', 'Completa Nombre, Apellido y Correo.');
        return;
      }
      if (rol === 'EDITOR') {
        const selEd = $('#invEditoriales');
        const tieneAlguna = selEd && selEd.selectedOptions && selEd.selectedOptions.length > 0;
        if (!tieneAlguna) {
          showAlert('warning', 'Selecciona al menos una editorial para el rol Editor.');
          return;
        }
      }

      const texto = `¿Deseas invitar al usuario: ${nombre} ${apellido} (${correo})?`;
      const ok = await confirmarInvitarModal(texto);
      if (!ok) return;

      // Preparar payload
      const editoriales = ($('#invEditoriales'))
        ? [...$('#invEditoriales').selectedOptions].map(o => o.value)
        : [];

      // CSRF
      const csrfInput = document.querySelector('#formInvitarUsuario input[name="csrfmiddlewaretoken"]');
      const csrf = csrfInput ? csrfInput.value : '';

      // URL desde patrón
      const url = (window.INVITAR_URL_PATTERN || '/panel/admin/usuarios/invitar/');

      try {
        const resp = await fetch(url, {
          method: 'POST',
          credentials: 'same-origin', // ⬅️ importante: manda cookies (sesión/CSRF)
          headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
          body: JSON.stringify({ nombre, apellido, correo, rol, editoriales, id_fiscal: idFiscal })
        });

        // Verificamos si el servidor devolvió JSON
        const contentType = resp.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          const html = await resp.text();
          showAlert('danger', 'Respuesta no válida del servidor.');
          console.error('Respuesta HTML:', html);
          return;
        }

        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          const msg = data.errors
            ? Object.entries(data.errors).map(([k, v]) => `${k}: ${v}`).join(' | ')
            : (data.error || 'No se pudo invitar al usuario.');
          showAlert('danger', msg);
          return;
        }

        modalInvitar.hide();
        if (typeof mostrarToast === 'function') {
          mostrarToast(`Invitación enviada a: ${correo}`, 'success', true);
        }
      } catch (e) {
        showAlert('danger', `Error de red: ${e}`);
      }
    });
  }
});
