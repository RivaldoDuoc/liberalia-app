document.addEventListener('DOMContentLoaded', function () {
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    const modalEl = document.getElementById('modalEditarUsuario');
    if (!modalEl) return;

    const modal = new bootstrap.Modal(modalEl);
    const alertBox = document.getElementById('editarAlert');

    function showAlert(kind, msg) {
        if (!alertBox) return;
        alertBox.className = `alert alert-${kind}`;
        alertBox.textContent = msg;
        alertBox.classList.remove('d-none');
    }
    function hideAlert() { if (alertBox) alertBox.classList.add('d-none'); }

    // Habilita/deshabilita selector de editoriales según rol 
    function toggleEditoriales(rol) {
        const grp = $('#grupoEditoriales');
        const sel = $('#editarEditoriales');
        if (!grp || !sel) return;
        const enable = (rol === 'EDITOR');
        sel.disabled = !enable;            // solo deshabilitar/habilitar
        grp.style.opacity = enable ? '1' : '.6';
    }

    // Abrir modal con datos al presionar "Editar" 
    $$('.btn-editar').forEach(btn => {
        btn.addEventListener('click', () => {
            hideAlert();

            // Cargar datos base
            $('#editarUserId').value = btn.dataset.userId || '';
            $('#editarUsername').value = btn.dataset.username || '';
            $('#editarEmail').value = btn.dataset.email || '';
            $('#editarNombre').value = btn.dataset.nombre || '';
            $('#editarApellido').value = btn.dataset.apellido || '';

            // Rol NORMALIZADO
            const rol = ((btn.dataset.rol || 'CONSULTOR').trim().toUpperCase());
            const esUnicoAdmin = btn.dataset.esUnicoAdmin === '1';

            // Setear y (si aplica) bloquear cambio de rol
            const selRol = $('#editarRol');
            if (selRol) {
                selRol.value = rol;
                selRol.disabled = esUnicoAdmin;   // único admin, no permite cambiar rol
            }

            // Mensaje informativo si es único admin
            const textoUnico = $('#textoUnicoAdmin');
            if (textoUnico) textoUnico.classList.toggle('d-none', !esUnicoAdmin);

            // Preseleccionar editoriales del usuario
            const seleccionadas = (btn.dataset.editoriales || '').split(',').filter(Boolean);
            const selEditoriales = $('#editarEditoriales');
            if (selEditoriales) {
                [...selEditoriales.options].forEach(o => o.selected = seleccionadas.includes(o.value));
            }

            // Activar/desactivar grupo editoriales según rol 
            toggleEditoriales(rol);

            // Atenuar el modal de edición cuando se abre el de confirmación
            document.getElementById('modalEditarUsuario')?.classList.add('modal-oscurecido');

            // Abrir modal
            modal.show();
        });
    });

    // Cambiar rol en el modal (activa/desactiva editoriales)
    const selRol = $('#editarRol');
    if (selRol) {
        selRol.addEventListener('change', (e) => {
            toggleEditoriales(e.target.value);
        });
    }

    // Guardar al Editar y confirmar

    function confirmarGuardarModal(mensaje) {
        return new Promise((resolve) => {
            const el = document.getElementById('modalConfirmGuardar');
            const msg = document.getElementById('confirmGuardarMensaje');
            const btn = document.getElementById('btnConfirmGuardar');
            if (!el || !msg || !btn) { resolve(false); return; }

            msg.textContent = mensaje;

            const modal = new bootstrap.Modal(el, {
                backdrop: 'static',
                keyboard: false
            });

            const onClick = () => { cleanup(); resolve(true); };
            const cleanup = () => {
                btn.removeEventListener('click', onClick);
                el.removeEventListener('hidden.bs.modal', onHide);
            };
            const onHide = () => { cleanup(); resolve(false); };

            btn.addEventListener('click', onClick, { once: true });
            el.addEventListener('hidden.bs.modal', onHide, { once: true });

            document.getElementById('modalEditarUsuario')?.classList.add('modal-oscurecido');
            modal.show();
        });
    }


    const btnGuardar = $('#btnGuardarEditar');
    if (btnGuardar) {
        btnGuardar.addEventListener('click', async () => {
            hideAlert();

            const username = ($('#editarUsername').value || '').trim();
            const nombre = ($('#editarNombre').value || '').trim();
            const apellido = ($('#editarApellido').value || '').trim();
            const nombreCompleto = `${nombre} ${apellido}`.trim() || username;

            const ok = await confirmarGuardarModal(`¿Deseas guardar los cambios del usuario: ${nombreCompleto}?`);
            if (!ok) return;

            const userId = $('#editarUserId').value;
            const rolActual = $('#editarRol').value;
            const selEd = $('#editarEditoriales');
            const editoriales = selEd ? [...selEd.selectedOptions].map(o => o.value) : [];

            const csrfInput = document.querySelector('#formEditarUsuario input[name="csrfmiddlewaretoken"]');
            const csrf = csrfInput ? csrfInput.value : '';

            const pattern = (window.EDITAR_URL_PATTERN || '/panel/admin/usuarios/0/editar/');
            const url = pattern.replace('/0/', `/${userId}/`);

            try {
            const resp = await fetch(url, {
              method: 'POST',
              credentials: 'same-origin',
              headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
              body: JSON.stringify({ nombre, apellido, correo, rol, editoriales, id_fiscal: idFiscal })
            });
                const data = await resp.json();
                if (!resp.ok || !data.ok) {
                    const msg = data.errors
                        ? Object.entries(data.errors).map(([k, v]) => `${k}: ${v}`).join(' | ')
                        : 'Error desconocido';
                    showAlert('danger', msg);
                    return;
                }
                showAlert('success', 'Cambios guardados correctamente.');
                setTimeout(() => window.location.reload(), 900);
            } catch (e) {
                showAlert('danger', `Error de red: ${e}`);
            }
        });
    }
});

// ======= Toggle con botones Habilitar/Deshabilitar =======

// Modal de confirmación 
function confirmarToggleModal(mensaje) {
  return new Promise((resolve) => {
    const el  = document.getElementById('modalConfirmToggle');
    const msg = document.getElementById('confirmToggleMensaje');
    const btn = document.getElementById('btnConfirmToggle');
    if (!el || !msg || !btn) { resolve(false); return; }

    msg.textContent = mensaje;

    const modal = new bootstrap.Modal(el, { backdrop: 'static', keyboard: false });

    const onClick = () => {
      modal.hide();
      cleanup();
      resolve(true);
    };
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

// Botones tooble (Activado / Desactivado)
document.querySelectorAll('.btn-toggle-estado').forEach(btn => {
  btn.addEventListener('click', async () => {
    const userId   = btn.dataset.userId;
    const activo   = btn.dataset.activo === '1';
    const nombre   = (btn.dataset.nombre || '').trim();
    const apellido = (btn.dataset.apellido || '').trim();
    const username = (btn.dataset.username || '').trim();
    const nombreCompleto = `${nombre} ${apellido}`.trim() || username;

    const accion = activo ? 'deshabilitar' : 'habilitar';
    const ok = await confirmarToggleModal(`¿Está seguro que desea ${accion} al usuario: ${nombreCompleto}?`);
    if (!ok) return;

    // Protección contra envíos falsos (CSRF)
    const csrfInput = document.querySelector('#formEditarUsuario input[name="csrfmiddlewaretoken"]');
    const csrf = csrfInput ? csrfInput.value : '';

    const pattern = (window.EDITAR_URL_PATTERN || '').replace('/editar/', '/toggle-activo/');
    const url = pattern.replace('/0/', `/${userId}/`);

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
        body: JSON.stringify({ activar: !activo })
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        const msg = data.error || 'No se pudo actualizar el estado del usuario.';
        mostrarToast(msg, 'error');  // ✔ usar toast bonito
        return;
      }

      // 1) Texto del botón + data-activo
      btn.textContent = data.is_active ? 'Deshabilitar' : 'Habilitar';
      btn.dataset.activo = data.is_active ? '1' : '0';

      // 2) Estilos de fila (gris para inactivo)
      const fila = btn.closest('tr');
      if (fila) {
        fila.classList.toggle('usuario-inactivo', !data.is_active);

        // 3) (Nuevo) Habilitar/Deshabilitar el botón "Editar" de ESTA fila
        const btnEditar = fila.querySelector('.btn-editar');
        if (btnEditar) {
          btnEditar.disabled = !data.is_active;
        }
      }

      // 4) Mostrar el mennsaje emergente con información habilitado / deshabilitado
        mostrarToast(
        `Usuario ${nombreCompleto}: ${data.is_active ? 'Habilitado' : 'Deshabilitado'}`,
        data.is_active ? 'success' : 'warning',
        true  // recargar al cerrar
        );

    } catch (e) {
      mostrarToast(`Error de red: ${e}`, 'error'); 
    }
  });
});


function mostrarToast(mensaje, tipo = 'info', recargarAlCerrar = false) {
  const toastBody = document.getElementById('toast-general-body');
  const toastEl = document.getElementById('toast-general');
  if (!toastBody || !toastEl) return;

  toastBody.textContent = mensaje;

  const colores = {
    info:    '#643c4aff',  
    success: '#198754',    
    error:   '#dc3545',    
    warning: '#ffc107'    
  };

  toastEl.style.backgroundColor = colores[tipo] || colores.info;
  toastEl.style.color = 'white';

  const bsToast = new bootstrap.Toast(toastEl, { delay: 1000 });

  // Recargar justo cuando el toast se oculta (tras 1s)
  if (recargarAlCerrar) {
    toastEl.addEventListener('hidden.bs.toast', () => {
      window.location.reload();
    }, { once: true });
  }

  bsToast.show();
}