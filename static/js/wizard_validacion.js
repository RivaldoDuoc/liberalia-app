
(function () {
  const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  // norm: limpia espacios/guiones y pasa a MAYÚSCULAS (útil para validar códigos)
  const norm = s => (s || "").toString().replace(/[\s-]+/g, "").toUpperCase();

  function ensureFeedbackEl(input) {
    // Busca un .invalid-feedback cercano; si no existe, lo crea
    let container = input.closest('.col-md-4, .col-md-6, .col-12') || input.parentElement;
    if (!container) container = input;
    let fb = container.querySelector('.invalid-feedback');
    if (!fb) {
      fb = document.createElement('div');
      fb.className = 'invalid-feedback d-block';
      container.appendChild(fb);
    }
    return fb;
  }

  // showError: marca el input como inválido y escribe el mensaje
  function showError(input, msg) {
    input.classList.add('is-invalid');
    const fb = ensureFeedbackEl(input);
    fb.textContent = msg;
  }
  // clearError: limpia el estado de error del input (y borra el texto del feedback)
  function clearError(input) {
    input.classList.remove('is-invalid');
    const container = input.closest('.col-md-4, .col-md-6, .col-12') || input.parentElement;
    const fb = container ? container.querySelector('.invalid-feedback') : null;
    if (fb) fb.textContent = '';
  }

   // === Validadores específicos (cálculo de dígitos verificadores) ===
   // ISBN-10: 9 números + dígito (puede ser X). Fórmula estándar mod 11.
  function isValidISBN10(code) {
    if (!/^\d{9}[\dX]$/.test(code)) return false;
    let sum = 0;
    for (let i = 0; i < 10; i++) {
      const ch = code[i] === 'X' ? 10 : parseInt(code[i], 10);
      sum += ch * (10 - i);
    }
    return sum % 11 === 0;
  }
  // EAN-13 (también sirve para ISBN-13): checksum con pesos 1/3 alternados
  function isValidEAN13(code) {
    if (!/^\d{13}$/.test(code)) return false;
    const digits = code.split('').map(Number);
    const checksum = digits.slice(0, 12).reduce((acc, d, i) => acc + d * (i % 2 ? 3 : 1), 0);
    const check = (10 - (checksum % 10)) % 10;
    return check === digits[12];
  }

  // === Reglas de validación por campo (según "name") ===
  async function validateField(input) {
    const name = input.name;
    const val = input.value;

    // ---- Paso 1: Identificación ----
    if (name === 'isbn') {
      const code = norm(val);
      if (!code) return showError(input, 'Este campo es obligatorio.'), false;
      if (code.length === 10) {
        if (!isValidISBN10(code)) return showError(input, 'ISBN-10 inválido'), false;
      } else if (code.length === 13) {
        if (!isValidEAN13(code)) return showError(input, 'ISBN-13 inválido'), false;
      } else {
        return showError(input, 'ISBN debe tener 10 o 13 caracteres.'), false;
      }
      return clearError(input), true;
    }
    if (name === 'ean') {
      const code = norm(val);
      if (!code) return clearError(input), true; // opcional
      if (!isValidEAN13(code)) return showError(input, 'EAN inválido'), false;
      return clearError(input), true;
    }
    if (name === 'editorial') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      return clearError(input), true;
    }
    if (name === 'titulo' || name === 'autor') {
      if (!val.trim()) return showError(input, 'Campo obligatorio.'), false;
      return clearError(input), true;
    }

    // ---- Paso 2: Ficha técnica ----
    if (name === 'tipo_tapa' || name === 'idioma_original' || name === 'pais_edicion') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      return clearError(input), true;
    }
    if (name === 'numero_paginas' || name === 'numero_edicion') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      const n = Number(val);
      if (!Number.isInteger(n) || n < 1) return showError(input, 'Número entero ≥ 1.'), false;
      return clearError(input), true;
    }
    if (name === 'fecha_edicion') {
      if (!val) return showError(input, 'Campo obligatorio'), false;
      return clearError(input), true;
    }
    // Son opcionales: si vienen, deben ser números >= 0
    if (name === 'alto_cm' || name === 'ancho_cm' || name === 'grosor_cm') {
      if (!val) return clearError(input), true;
      const n = Number(val);
      if (!Number.isFinite(n) || n < 0) return showError(input, 'Número ≥ 0).'), false;
      return clearError(input), true;
    }
    if (name === 'peso_gr') {
      if (!val) return clearError(input), true;
      const n = Number(val);
      if (!Number.isInteger(n) || n < 0) return showError(input, 'Número entero ≥ 0).'), false;
      return clearError(input), true;
    }

    // ---- Paso 3: Comercial ----
    if (name === 'precio') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      const n = Number(val);
      if (!Number.isFinite(n) || n < 0) return showError(input, 'Ingrese un precio ≥ 0'), false;
      return clearError(input), true;
    }
    if (name === 'moneda') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      return clearError(input), true;
    }
    if (name === 'descuento_distribuidor') {
      if (!val) return showError(input, 'Campo obligatorio.'), false;
      const n = Number(val);
      if (!Number.isFinite(n) || n < 0 || n > 99.9) return showError(input, 'Descuento debe estar entre 0.0 y 99.9%.'), false;
      return clearError(input), true;
    }
    if (name === 'resumen_libro') {
      if (!val.trim()) return showError(input, 'Campo obligatorio.'), false;
      return clearError(input), true;
    }

    // Cualquier otro campo (normalmente opcional): limpio y doy OK
    return clearError(input), true;
  }

  // === Enlaces de eventos (bindings) ===
  const form = document.getElementById('wizardForm');
  if (!form) return; // Si no hay form en la página, no hago nada

  // cuando el usuario sale del campo, valido y muestro error si corresponde
  form.addEventListener('blur', (e) => {
    if (e.target && e.target.name) validateField(e.target);
  }, true);

  // input: si el campo estaba inválido, revalido al teclear para limpiar apenas esté bien
  form.addEventListener('input', (e) => {
    if (e.target && e.target.classList.contains('is-invalid')) {
      validateField(e.target); // revalida y limpia si ya es OK
    }
  });

  // submit: antes de enviar, valido todo el formulario; si algo falla, detengo envío
  form.addEventListener('submit', async (e) => {
    const fields = $$('input, select, textarea', form).filter(el => el.name);
    let ok = true;
    for (const el of fields) {
      const valid = await validateField(el);
      if (!valid) ok = false;
    }
    if (!ok) {
      e.preventDefault();
      e.stopPropagation();
      const firstBad = form.querySelector('.is-invalid');
      if (firstBad) firstBad.focus();
    }
  });






 (function () {
    const btn = document.getElementById('btnPickImg');
    const fileInput = document.getElementById('pickImgInput');
    const hiddenCodigo = document.getElementById('id_codigo_imagen');
    const namePreview = document.getElementById('pickImgName');

    // ISBN guardado en sesión (paso Ident del wizard)
    const ISBN_FROM_SESSION = "{{ wizard_data.ident.isbn|default:'' }}";

    if (btn && fileInput && hiddenCodigo && namePreview) {
      btn.addEventListener('click', () => fileInput.click());

      fileInput.addEventListener('change', function () {
        if (!this.files || !this.files.length) return;

        const fname = this.files[0].name || "";
        namePreview.textContent = fname;

        const ext = (fname.split('.').pop() || "").toLowerCase();
        if (!['png', 'jpg', 'jpeg'].includes(ext)) {
          alert("Formato no permitido. Usa PNG, JPG o JPEG.");
          this.value = "";
          namePreview.textContent = "";
          hiddenCodigo.value = ""; // la vista usará ISBN.png si queda vacío
          return;
        }

        const base =
          (ISBN_FROM_SESSION || "").trim() ||
          (hiddenCodigo.value.includes('.') ? hiddenCodigo.value.split('.')[0] : "") ||
          "ISBN";

        const normalizedExt = (ext === 'jpeg') ? 'jpg' : ext;
        hiddenCodigo.value = `${base}.${normalizedExt}`;
      });
    }
  })();

  
})();

// Exponer validadores reutilizables para uso por otros scripts (p.ej. carga masiva)
(function () {
  // Reuse helpers defined above where possible; redefine minimal helpers to avoid scope issues
  const norm = s => (s || "").toString().replace(/[\s-]+/g, "").toUpperCase();

  function isValidISBN10(code) {
    if (!/^[0-9]{9}[0-9X]$/.test(code)) return false;
    let sum = 0;
    for (let i = 0; i < 10; i++) {
      const ch = code[i] === 'X' ? 10 : parseInt(code[i], 10);
      sum += ch * (10 - i);
    }
    return sum % 11 === 0;
  }
  function isValidEAN13(code) {
    if (!/^\d{13}$/.test(code)) return false;
    const digits = code.split('').map(Number);
    const checksum = digits.slice(0, 12).reduce((acc, d, i) => acc + d * (i % 2 ? 3 : 1), 0);
    const check = (10 - (checksum % 10)) % 10;
    return check === digits[12];
  }

  function validateRowObject(row) {
    // row: object with keys normalized to snake_case lowercase (ex: 'isbn', 'tipo_tapa')
    const errors = {};
    // isbn
    const isbn = (row.isbn || '').toString().trim();
    const isbnNorm = norm(isbn);
    // if (!isbnNorm) errors.isbn = 'ISBN obligatorio.';
    // else if (isbnNorm.length === 10) { if (!isValidISBN10(isbnNorm)) errors.isbn = 'ISBN-10 inválido.'; }
    // else if (isbnNorm.length === 13) { if (!isValidEAN13(isbnNorm)) errors.isbn = 'ISBN-13 inválido.'; }
    // else errors.isbn = 'ISBN debe tener 10 o 13 caracteres.';

    // ean optional
    const ean = (row.ean || '').toString().trim();
    if (ean) {
      const en = ean.replace(/\D/g, '');
      if (en && en.length === 13 && !isValidEAN13(en)) errors.ean = 'EAN inválido.';
    }

    // editorial
    if (!row.editorial || String(row.editorial).trim() === '') errors.editorial = 'Editorial obligatoria.';

    // titulo/autor
    if (!row.titulo || String(row.titulo).trim() === '') errors.titulo = 'Título obligatorio.';
    if (!row.autor || String(row.autor).trim() === '') errors.autor = 'Autor obligatorio.';

    // tipo_tapa, idioma_original, pais_edicion required
    if (!row.tipo_tapa || String(row.tipo_tapa).trim() === '') errors.tipo_tapa = 'Tipo tapa obligatorio.';
    if (!row.idioma_original || String(row.idioma_original).trim() === '') errors.idioma_original = 'Idioma obligatorio.';
    if (!row.pais_edicion || String(row.pais_edicion).trim() === '') errors.pais_edicion = 'País edición obligatorio.';

    // numero_paginas, numero_edicion
    const np = Number(row.numero_paginas);
    if (!row.numero_paginas || !Number.isInteger(np) || np < 1) errors.numero_paginas = 'Número de páginas entero ≥ 1.';
    const ne = Number(row.numero_edicion);
    if (!row.numero_edicion || !Number.isInteger(ne) || ne < 1) errors.numero_edicion = 'Número edición entero ≥ 1.';

    // fecha_edicion accept ISO yyyy-mm-dd or try parse
    const fech = row.fecha_edicion;
    let fecha_ok = false;
    if (fech === null || fech === undefined || String(fech).trim() === '') {
      fecha_ok = false;
    } else if (typeof fech === 'string') {
      fecha_ok = /^\d{4}-\d{2}-\d{2}$/.test(fech.trim());
    } else if (typeof fech === 'number') {
      // excel serial; accept and leave to server
      fecha_ok = true;
    } else if (fech instanceof Date) fecha_ok = true;
    if (!fecha_ok) errors.fecha_edicion = 'Fecha edición inválida.';

    // precio
    const precio = Number(row.precio);
    if (row.precio === null || row.precio === undefined || row.precio === '') errors.precio = 'Precio obligatorio.';
    else if (!Number.isFinite(precio) || precio < 0) errors.precio = 'Precio debe ser ≥ 0.';

    // moneda
    if (!row.moneda || String(row.moneda).trim() === '') errors.moneda = 'Moneda obligatoria.';

    // descuento_distribuidor
    const desc = Number(row.descuento_distribuidor);
    if (row.descuento_distribuidor === null || row.descuento_distribuidor === undefined || row.descuento_distribuidor === '') errors.descuento_distribuidor = 'Descuento obligatorio.';
    else if (!Number.isFinite(desc) || desc < 0 || desc > 99.9) errors.descuento_distribuidor = 'Descuento debe estar entre 0.0 y 99.9.';

    // resumen_libro
    if (!row.resumen_libro || String(row.resumen_libro).trim() === '') errors.resumen_libro = 'Resumen obligatorio.';

    const ok = Object.keys(errors).length === 0;
    return { ok, errors };
  }

  window.LibroValidators = window.LibroValidators || {};
  window.LibroValidators.validateRow = validateRowObject;
})();
