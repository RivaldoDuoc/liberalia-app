document.addEventListener('DOMContentLoaded', function () {
  const $ = (s) => document.querySelector(s);
  const fileInput = $('#cargaMasivaFile');
  const btnCargar = $('#btnCargarFile');
  const btnEnviar = $('#btnEnviarCarga');
  const filenameEl = $('#cargaMasivaFilename');
  const erroresEl = $('#cargaMasivaErrors');

  let parsedRows = null; // array of objects

  if (!fileInput || !btnCargar || !btnEnviar) return;

  // Helper CSRF
  function getCSRF() {
    // 1) input hidden en la página
    const el = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    // 2) window global (plantilla puede inyectarlo)
    if (window.CSRF_TOKEN) return window.CSRF_TOKEN;
    // 3) cookie fallback (Django default 'csrftoken')
    const match = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
    if (match) return match.pop();
    return '';
  }

  btnCargar.addEventListener('click', () => {
    // Limpio el valor previo para asegurar que seleccionar el mismo archivo vuelva a disparar 'change'
    try { fileInput.value = ''; } catch (e) { fileInput.value = null; }
    fileInput.click();
  });

  fileInput.addEventListener('change', async (ev) => {
    erroresEl.textContent = '';
    parsedRows = null;
    btnEnviar.disabled = true;
    const f = ev.target.files && ev.target.files[0];
    if (!f) return;
    filenameEl.textContent = `Archivo: ${f.name}`;

    try {
      const data = await f.arrayBuffer();
      const workbook = XLSX.read(data, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      const ws = workbook.Sheets[sheetName];
      const rawRows = XLSX.utils.sheet_to_json(ws, { defval: null });

      // Excel header examples (mayúsculas/espacios) -> claves internas en snake_case minúsculas
      const headerMap = {
        'isbn': 'isbn', 'ean': 'ean', 'editorial': 'editorial', 'titulo': 'titulo', 'subtitulo': 'subtitulo', 'autor': 'autor', 'autor prologo': 'autor_prologo', 'autor_prologo': 'autor_prologo', 'traductor': 'traductor', 'ilustrador': 'ilustrador', 'tipo tapa': 'tipo_tapa', 'tipo_tapa': 'tipo_tapa', 'numero paginas': 'numero_paginas', 'numero_paginas': 'numero_paginas', 'alto cm': 'alto_cm', 'alto_cm': 'alto_cm', 'ancho cm': 'ancho_cm', 'ancho_cm': 'ancho_cm', 'grosor cm': 'grosor_cm', 'grosor_cm': 'grosor_cm', 'peso gr': 'peso_gr', 'peso_gr': 'peso_gr', 'idioma original': 'idioma_original', 'idioma_original': 'idioma_original', 'numero edicion': 'numero_edicion', 'numero_edicion': 'numero_edicion', 'fecha edicion': 'fecha_edicion', 'fecha_edicion': 'fecha_edicion', 'pais edicion': 'pais_edicion', 'pais_edicion': 'pais_edicion', 'numero impresion': 'numero_impresion', 'numero_impresion': 'numero_impresion', 'tematica': 'tematica', 'precio': 'precio', 'moneda': 'moneda', 'descuento distribuidor': 'descuento_distribuidor', 'descuento_distribuidor': 'descuento_distribuidor', 'resumen libro': 'resumen_libro', 'resumen_libro': 'resumen_libro', 'rango etario': 'rango_etario', 'rango_etario': 'rango_etario'
      };

      if (!rawRows || !rawRows.length) {
        erroresEl.classList.remove('text-success');
        erroresEl.classList.add('text-danger');
        erroresEl.textContent = 'La hoja seleccionada está vacía.';
        try { fileInput.value = ''; } catch (e) { fileInput.value = null; }
        return;
      }

      // Construir filas normalizadas
      const normRows = rawRows.map((r, idx) => {
        const out = {};
        Object.entries(r).forEach(([k, v]) => {
          const key = (k || '').toString().trim().toLowerCase();
          const mapped = headerMap[key] || key.replace(/\s+/g, '_');
          out[mapped] = v;
        });
        out._row = idx + 2; // header in row 1
        return out;
      });

      // Validación por fila usando validadores reutilizables
      const clientValidator = window.LibroValidators && window.LibroValidators.validateRow;
      const errors = [];
      for (const row of normRows) {
        if (clientValidator) {
          const res = clientValidator(row);
          if (!res.ok) {
            errors.push(`Fila ${row._row}: ${Object.entries(res.errors).map(([k,v])=>`${k}: ${v}`).join('; ')}`);
          }
        } else {
          // fallback básico
          if (!row.isbn) errors.push(`Fila ${row._row}: ISBN vacío`);
          if (!row.titulo) errors.push(`Fila ${row._row}: titulo vacío`);
        }
      }

      if (errors.length) {
        erroresEl.classList.remove('text-success');
        erroresEl.classList.add('text-danger');
        erroresEl.textContent = errors.join('\n');
        try { fileInput.value = ''; } catch (e) { fileInput.value = null; }
        return;
      }

  parsedRows = normRows;
  erroresEl.classList.remove('text-danger');
  erroresEl.classList.add('text-success');
  erroresEl.textContent = `Validación OK: ${parsedRows.length} filas detectadas. Puede presionar Enviar.`;
  btnEnviar.disabled = false;
  // Limpiamos el input para permitir re-seleccionar el mismo archivo si el usuario lo desea
  try { fileInput.value = ''; } catch (e) { fileInput.value = null; }

    } catch (e) {
      erroresEl.textContent = `Error al leer archivo: ${e.message || e}`;
    }
  });

  btnEnviar.addEventListener('click', async () => {
    if (!parsedRows) return;
    btnEnviar.disabled = true;
    erroresEl.textContent = 'Enviando...';
    try {
  const url = (window.UPLOAD_JSON_URL || '/panel/editor/fichas/upload-json/');
  console.log(">>> upload_fichas_json called");
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRF(),
        },
        body: JSON.stringify({ rows: parsedRows.map(r => {
          // eliminar clave interna
          const copy = { ...r };
          delete copy._row;
          return copy;
        }) })
      });

      const data = await resp.json();
      if (!resp.ok) {
        // Mostrar solo mensajes amigables al usuario (no exponer datos internos)
        if (data && data.errors && Array.isArray(data.errors)) {
          erroresEl.classList.remove('text-success');
          erroresEl.classList.add('text-danger');
          erroresEl.textContent = data.errors.map(e => `Fila ${e.row || '?'}: ${e.error || 'Error'}`).join('\n');
        } else if (data && data.error) {
          erroresEl.classList.remove('text-success');
          erroresEl.classList.add('text-danger');
          erroresEl.textContent = data.error;
        } else {
          erroresEl.classList.remove('text-success');
          erroresEl.classList.add('text-danger');
          erroresEl.textContent = `Error: ${resp.status}`;
        }
        btnEnviar.disabled = false;
        return;
      }

      if (!data.ok) {
        erroresEl.textContent = data.errors ? JSON.stringify(data.errors, null, 2) : 'Error desconocido';
        btnEnviar.disabled = false;
        return;
      }

      // Mostrar resumen y errores detallados (si los hay)
      const created = data.created || 0;
      const failed = data.failed || 0;
      if (failed > 0) {
        erroresEl.classList.remove('text-success');
        erroresEl.classList.add('text-danger');
        let txt = `Carga parcial. Creados: ${created}. Fallidos: ${failed}\n`;
        if (data.errors && Array.isArray(data.errors)) {
          txt += data.errors.map(e => `Fila ${e.row || '?'}: ${e.error || 'Error'}`).join('\n');
        }
        erroresEl.textContent = txt;
        btnEnviar.disabled = false;
        return; // no recargar
      }

      // Todo OK
      erroresEl.classList.remove('text-danger');
      erroresEl.classList.add('text-success');
      erroresEl.textContent = `Carga finalizada. Registros creados: ${created}.`;
      setTimeout(() => window.location.reload(), 900);
    } catch (e) {
      erroresEl.textContent = `Error de red: ${e}`;
      btnEnviar.disabled = false;
    }
  });
});
