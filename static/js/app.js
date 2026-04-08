// ============================================================
// BIZNES REJA PLATFORMASI v2.0 — Frontend Logic
// 480 ta reja | Autocomplete | Faoliyat turi | Preview | To'lov
// ============================================================
let currentStep = 1;
const totalSteps = 8;
let calcTimeout, analysisTimeout;
let categoriesData = null;
let allPlans = [];
let selectedFaoliyat = '';
let selectedPaymentMethod = 'demo';
let previewData = null;

// ============================================================
// INIT — Kategoriyalar yuklash
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const resp = await fetch('/api/categories');
    const json = await resp.json();
    if (json.success) {
      categoriesData = json.data;
      allPlans = json.data.barcha_rejalar || [];
      console.log(`✅ ${allPlans.length} ta reja yuklandi`);
    }
  } catch (e) {
    console.warn('Kategoriyalar yuklanmadi:', e);
  }

  // Stepper clicks
  document.querySelectorAll('.step-item').forEach(item => {
    item.addEventListener('click', () => {
      const s = +item.dataset.step;
      if (s < currentStep) goToStep(s);
      else if (s === currentStep + 1) nextStep(s);
    });
  });

  // Input error cleanup
  document.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', () => {
      inp.closest('.input-group')?.classList.remove('has-error');
      inp.classList.remove('error');
    });
  });

  // Upload setup
  setupUpload('uploadBizImg', 'business_image');
  setupUpload('uploadProduct', 'product_photo');

  // Autocomplete setup
  setupAutocomplete();

  // Form submit
  setupFormSubmit();
});

// ============================================================
// STEPPER
// ============================================================
function goToStep(s) {
  document.querySelectorAll('.form-section').forEach(el => el.classList.remove('active'));
  document.getElementById('step' + s).classList.add('active');
  document.querySelectorAll('.step-item').forEach(item => {
    const n = +item.dataset.step;
    item.classList.remove('active', 'completed');
    if (n === s) item.classList.add('active');
    else if (n < s) item.classList.add('completed');
  });
  for (let i = 1; i < totalSteps; i++) {
    const line = document.getElementById('line' + i);
    if (line) {
      line.classList.remove('active', 'completed');
      if (i < s) line.classList.add('completed');
      else if (i === s) line.classList.add('active');
    }
  }
  currentStep = s;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function nextStep(s) { if (!validateStep(currentStep)) return; hideAlert(); goToStep(s); }
function prevStep(s) { hideAlert(); goToStep(s); }

// ============================================================
// VALIDATION
// ============================================================
function validateStep(step) {
  const sec = document.getElementById('step' + step);
  if (!sec) return true;
  const inputs = sec.querySelectorAll('input[required]');
  let ok = true;
  inputs.forEach(inp => {
    const g = inp.closest('.input-group');
    if (!inp.value.trim()) { g.classList.add('has-error'); inp.classList.add('error'); ok = false; }
    else { g.classList.remove('has-error'); inp.classList.remove('error'); }
  });

  // Step 1: faoliyat turi tekshirish
  if (step === 1 && !selectedFaoliyat) {
    showAlert("Iltimos, biznes faoliyat turini tanlang");
    ok = false;
  }

  if (!ok) showAlert("Iltimos, majburiy maydonlarni to'ldiring");
  return ok;
}

// ============================================================
// AUTOCOMPLETE (480 ta reja qidirish)
// ============================================================
function setupAutocomplete() {
  const input = document.getElementById('loyiha_nomi');
  const dropdown = document.getElementById('autocompleteDropdown');
  if (!input || !dropdown) return;

  let selectedIndex = -1;

  input.addEventListener('input', () => {
    const query = input.value.trim().toLowerCase();
    if (query.length < 2) { dropdown.classList.remove('show'); return; }

    const results = allPlans.filter(p => p.nomi.toLowerCase().includes(query)).slice(0, 20);
    
    if (results.length === 0) {
      dropdown.innerHTML = '<div class="autocomplete-no-result">Natija topilmadi. Siz o\'zingiz yozishingiz mumkin.</div>';
      dropdown.classList.add('show');
      return;
    }

    selectedIndex = -1;
    dropdown.innerHTML = results.map((r, i) => `
      <div class="autocomplete-item" data-index="${i}" data-name="${r.nomi}" data-faoliyat="${r.faoliyat_turi}">
        <div>
          <div class="ac-name">${highlightMatch(r.nomi, query)}</div>
          <div class="ac-cat">${r.kategoriya}</div>
        </div>
        <span class="ac-badge">${r.faoliyat_nomi}</span>
      </div>
    `).join('');
    dropdown.classList.add('show');

    // Click on item
    dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('click', () => {
        input.value = item.dataset.name;
        const ft = item.dataset.faoliyat;
        if (ft) selectFaoliyat(ft);
        dropdown.classList.remove('show');
      });
    });
  });

  // Keyboard navigation
  input.addEventListener('keydown', (e) => {
    const items = dropdown.querySelectorAll('.autocomplete-item');
    if (!items.length) return;
    
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
      items.forEach((it, i) => it.classList.toggle('selected', i === selectedIndex));
      items[selectedIndex]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      items.forEach((it, i) => it.classList.toggle('selected', i === selectedIndex));
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      const sel = items[selectedIndex];
      input.value = sel.dataset.name;
      if (sel.dataset.faoliyat) selectFaoliyat(sel.dataset.faoliyat);
      dropdown.classList.remove('show');
    } else if (e.key === 'Escape') {
      dropdown.classList.remove('show');
    }
  });

  // Click outside closes
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.autocomplete-wrapper')) dropdown.classList.remove('show');
  });
}

function highlightMatch(text, query) {
  const idx = text.toLowerCase().indexOf(query);
  if (idx === -1) return text;
  return text.slice(0, idx) + '<strong style="color:var(--accent-l)">' + text.slice(idx, idx + query.length) + '</strong>' + text.slice(idx + query.length);
}

// ============================================================
// FAOLIYAT TURI TANLASH
// ============================================================
function selectFaoliyat(type) {
  selectedFaoliyat = type;
  document.getElementById('faoliyat_turi_hidden').value = type;

  // Update cards
  document.querySelectorAll('.faoliyat-card').forEach(card => {
    card.classList.toggle('active', card.dataset.type === type);
  });

  // Update Step 4 labels dynamically
  updateStep4ForType(type);
}

function updateStep4ForType(type) {
  if (!categoriesData) return;
  const ft = categoriesData.faoliyat_turlari[type];
  if (!ft) return;

  // Update labels
  const mahsulotLabel = document.getElementById('mahsulotLabel');
  const hajmLabel = document.getElementById('hajmLabel');
  const narxLabel = document.getElementById('narxLabel');
  const step4Title = document.getElementById('step4Title');
  const step4Desc = document.getElementById('step4Desc');

  if (mahsulotLabel) mahsulotLabel.textContent = ft.mahsulot_label;
  if (hajmLabel) hajmLabel.textContent = ft.hajm_label;
  if (narxLabel) narxLabel.textContent = ft.narx_label;

  const titles = {
    'ishlab_chiqarish': '🏭 Ishlab chiqarish ma\'lumotlari',
    'qishloq_xojaligi': '🌾 Qishloq xo\'jaligi ma\'lumotlari',
    'savdo': '🏪 Savdo biznesi ma\'lumotlari',
    'xizmat': '🍽 Xizmat ko\'rsatish ma\'lumotlari',
  };
  if (step4Title) step4Title.textContent = titles[type] || 'Mahsulot / Xizmat';
  if (step4Desc) step4Desc.textContent = ft.tavsif || 'Ma\'lumotlarni kiriting';

  // Dinamik qo'shimcha fieldlar
  const container = document.getElementById('dynamicFields');
  if (!container || !ft.qoshimcha_fieldlar) return;
  
  container.innerHTML = ft.qoshimcha_fieldlar.map(f => `
    <div class="input-group">
      <label>${f.label}</label>
      <div class="input-wrapper">
        <input type="number" step="any" name="${f.name}" placeholder="${f.placeholder}">
        <span class="sfx">${f.suffix}</span>
      </div>
    </div>
  `).join('');
}

// ============================================================
// KREDIT KALKULYATOR (real-time)
// ============================================================
function updateCalc() {
  clearTimeout(calcTimeout);
  calcTimeout = setTimeout(() => {
    const kredit = parseFloat(document.getElementById('kredit_input')?.value) || 0;
    const foiz = parseFloat(document.getElementById('foiz_input')?.value) || 0;
    const muddat = parseInt(document.getElementById('muddat_input')?.value) || 1;
    const imtiyoz = parseInt(document.getElementById('imtiyoz_input')?.value) || 0;
    const turi = document.querySelector('input[name="kredit_turi"]:checked')?.value || 'annuitet';

    if (kredit <= 0 || muddat <= 0) { setCalcValues(0, 0, 0); clearSchedule(); return; }

    const r = foiz / 12 / 100;
    const asosiy = muddat - imtiyoz;
    let oylik, jami, foizT;

    if (turi === 'annuitet') {
      if (foiz === 0) { oylik = kredit / (asosiy > 0 ? asosiy : muddat); }
      else if (asosiy > 0) { oylik = kredit * (r * Math.pow(1+r, asosiy)) / (Math.pow(1+r, asosiy) - 1); }
      else { oylik = kredit * (r * Math.pow(1+r, muddat)) / (Math.pow(1+r, muddat) - 1); }
      const imtPayment = kredit * r;
      jami = (imtiyoz * imtPayment) + (asosiy * oylik);
      foizT = jami - kredit;
    } else {
      const asosiyBolag = kredit / (asosiy > 0 ? asosiy : muddat);
      let q = kredit, j = 0, f = 0;
      for (let i = 0; i < imtiyoz; i++) { const fp = q * r; j += fp; f += fp; }
      for (let i = 0; i < asosiy; i++) { const fp = q * r; j += asosiyBolag + fp; f += fp; q -= asosiyBolag; }
      oylik = asosiy > 0 ? (kredit / asosiy + kredit * r) : 0;
      jami = j; foizT = f;
    }

    setCalcValues(oylik, jami, foizT);
    generateScheduleTable(kredit, foiz, muddat, imtiyoz, turi);
  }, 200);
}

function setCalcValues(oylik, jami, foiz) {
  const el = (id) => document.getElementById(id);
  if (el('calcOylik')) el('calcOylik').textContent = fmt(oylik);
  if (el('calcJami')) el('calcJami').textContent = fmt(jami);
  if (el('calcFoiz')) el('calcFoiz').textContent = fmt(foiz);
}

function generateScheduleTable(kredit, foiz, muddat, imtiyoz, turi) {
  const wrap = document.getElementById('scheduleWrap');
  if (!wrap) return;
  if (kredit <= 0 || muddat <= 0) { wrap.innerHTML = ''; return; }

  const r = foiz / 12 / 100;
  const asosiy = muddat - imtiyoz;
  let rows = [];
  let q = kredit;

  if (turi === 'annuitet') {
    let ann = 0;
    if (foiz === 0) ann = kredit / (asosiy > 0 ? asosiy : muddat);
    else if (asosiy > 0) ann = kredit * (r * Math.pow(1+r,asosiy)) / (Math.pow(1+r,asosiy)-1);

    for (let i = 1; i <= muddat; i++) {
      const fp = q * r;
      if (i <= imtiyoz) {
        rows.push({oy:i, tolov:fp, asosiy:0, foiz:fp, qoldiq:q, imt:true});
      } else {
        const ap = ann - fp;
        q -= ap;
        if (q < 1) q = 0;
        rows.push({oy:i, tolov:ann, asosiy:ap, foiz:fp, qoldiq:q, imt:false});
      }
    }
  } else {
    const ab = kredit / (asosiy > 0 ? asosiy : muddat);
    for (let i = 1; i <= muddat; i++) {
      const fp = q * r;
      if (i <= imtiyoz) {
        rows.push({oy:i, tolov:fp, asosiy:0, foiz:fp, qoldiq:q, imt:true});
      } else {
        q -= ab;
        if (q < 1) q = 0;
        rows.push({oy:i, tolov:ab+fp, asosiy:ab, foiz:fp, qoldiq:q, imt:false});
      }
    }
  }

  let displayRows = rows;
  if (rows.length > 20) {
    displayRows = [...rows.slice(0, 12), null, ...rows.slice(-3)];
  }

  let html = '<table class="schedule-table"><thead><tr><th>Oy</th><th>To\'lov</th><th>Asosiy</th><th>Foiz</th><th>Qoldiq</th></tr></thead><tbody>';
  for (const row of displayRows) {
    if (!row) {
      html += `<tr><td colspan="5" style="color:var(--text-3);font-style:italic">... ${rows.length - 15} qator yashirilgan ...</td></tr>`;
      continue;
    }
    const cls = row.imt ? ' class="imtiyoz"' : '';
    html += `<tr${cls}><td>${row.oy}</td><td>${fmt(row.tolov)}</td><td>${fmt(row.asosiy)}</td><td>${fmt(row.foiz)}</td><td>${fmt(row.qoldiq)}</td></tr>`;
  }
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

function clearSchedule() {
  const w = document.getElementById('scheduleWrap');
  if (w) w.innerHTML = '';
}

// ============================================================
// MOLIYAVIY TAHLIL (real-time)
// ============================================================
function updateAnalysis() {
  clearTimeout(analysisTimeout);
  analysisTimeout = setTimeout(() => {
    const get = id => parseFloat(document.getElementById(id)?.value) || 0;
    const loyiha = get('loyiha_qiymati');
    const hajm = get('hajm_input');
    const narx = get('narx_input');
    const yillikDaromad = hajm * narx;

    const kredit = get('kredit_input');
    const foiz = get('foiz_input');
    const muddat = parseInt(document.getElementById('muddat_input')?.value) || 12;

    if (loyiha <= 0 || yillikDaromad <= 0) return;

    const muddatYil = Math.max(Math.floor(muddat / 12), 1);

    // Faoliyat turiga qarab margin
    let margin = 0.25; // default
    if (selectedFaoliyat === 'ishlab_chiqarish') margin = 0.22;
    else if (selectedFaoliyat === 'qishloq_xojaligi') margin = 0.30;
    else if (selectedFaoliyat === 'savdo') margin = 0.15;
    else if (selectedFaoliyat === 'xizmat') margin = 0.40;

    const npvEl = document.getElementById('npvValue');
    const roiEl = document.getElementById('roiValue');
    const paybackEl = document.getElementById('paybackValue');
    const revenueEl = document.getElementById('revenueValue');

    if (npvEl) {
      const r = foiz / 100 || 0.15;
      let npvVal = -loyiha;
      for (let t = 1; t <= muddatYil; t++) {
        npvVal += yillikDaromad * margin / Math.pow(1 + r, t);
      }
      npvEl.textContent = fmt(npvVal);
      npvEl.closest('.calc-item')?.classList.toggle('hl', npvVal > 0);
      npvEl.closest('.calc-item')?.classList.toggle('er', npvVal <= 0);
    }
    if (roiEl) {
      const roiVal = ((yillikDaromad * margin * muddatYil) / loyiha * 100);
      roiEl.textContent = roiVal.toFixed(1) + '%';
    }
    if (paybackEl) {
      const pb = loyiha / (yillikDaromad * margin);
      paybackEl.textContent = pb.toFixed(1) + ' yil';
    }
    if (revenueEl) {
      revenueEl.textContent = fmt(yillikDaromad);
    }
  }, 300);
}

// ============================================================
// FILE UPLOAD
// ============================================================
function setupUpload(areaId, inputId) {
  const area = document.getElementById(areaId);
  const input = document.getElementById(inputId);
  if (!area || !input) return;

  area.addEventListener('click', () => input.click());
  area.addEventListener('dragover', e => { e.preventDefault(); area.style.borderColor = 'var(--accent)'; });
  area.addEventListener('dragleave', () => { area.style.borderColor = ''; });
  area.addEventListener('drop', e => {
    e.preventDefault();
    area.style.borderColor = '';
    input.files = e.dataTransfer.files;
    showPreview(area, input.files);
  });
  input.addEventListener('change', () => showPreview(area, input.files));
}

function showPreview(area, files) {
  let preview = area.querySelector('.upload-preview');
  if (!preview) { preview = document.createElement('div'); preview.className = 'upload-preview'; area.appendChild(preview); }
  preview.innerHTML = '';
  for (const f of files) {
    if (f.type.startsWith('image/')) {
      const div = document.createElement('div'); div.className = 'preview-item';
      const img = document.createElement('img'); img.src = URL.createObjectURL(f);
      div.appendChild(img); preview.appendChild(div);
    } else {
      const div = document.createElement('div'); div.className = 'preview-item';
      div.style.cssText = 'display:flex;align-items:center;justify-content:center;font-size:10px;color:var(--text-2);width:auto;padding:4px 8px';
      div.textContent = f.name.slice(0, 15); preview.appendChild(div);
    }
  }
}

// ============================================================
// PREVIEW GENERATION
// ============================================================
async function generatePreview() {
  if (!validateStep(currentStep)) return;
  hideAlert();
  goToStep(8);

  const container = document.getElementById('previewContent');
  container.innerHTML = '<div class="preview-loading"><div class="spinner" style="width:30px;height:30px;margin:0 auto 10px"></div><p>Preview tayyorlanmoqda...</p></div>';

  try {
    // Collect form data
    const formData = {};
    const form = document.getElementById('biznesForm');
    new FormData(form).forEach((v, k) => { if (k !== 'csrf_token' && typeof v === 'string') formData[k] = v; });

    const resp = await fetch('/api/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    const json = await resp.json();

    if (!json.success) {
      container.innerHTML = `<div class="preview-loading"><p style="color:var(--error)">Xatolik: ${json.error || 'Noma\'lum xatolik'}</p></div>`;
      return;
    }

    previewData = json.data;
    renderPreview(previewData, container);
    
    // Show payment section
    document.getElementById('paymentSection').style.display = 'block';
  } catch (e) {
    container.innerHTML = `<div class="preview-loading"><p style="color:var(--error)">Server bilan aloqa uzildi: ${e.message}</p></div>`;
  }
}

function renderPreview(data, container) {
  const ctx = data.context || {};
  const tables = data.tables || [];
  const ind = data.indicators || {};

  let html = '';

  // -- Loyiha ma'lumotlari --
  html += `<div class="preview-section">
    <h3>📋 Loyiha ma'lumotlari</h3>
    ${previewField('Loyiha nomi', ctx.loyiha_nomi, 'loyiha_nomi')}
    ${previewField('Tashabbuskor', ctx.tashabbuskor, 'tashabbuskor')}
    ${previewField('Faoliyat turi', data.faoliyat_nomi)}
    ${previewField('Manzil', ctx.manzil, 'manzil')}
    ${previewField('Bank', ctx.bank, 'bank')}
    ${previewField('Yuridik maqomi', ctx.mulk)}
    ${previewField('Rahbar F.I.SH', ctx.fio)}
  </div>`;

  // -- Moliyaviy ko'rsatkichlar --
  html += `<div class="preview-section">
    <h3>📈 Moliyaviy ko'rsatkichlar</h3>
    ${previewField('Loyiha qiymati', fmtNum(ctx.loyiha_qiymati) + " so'm", 'loyiha_qiymati')}
    ${previewField("O'z mablag'i", fmtNum(ctx.oz_mablag) + " so'm")}
    ${previewField('Bank krediti', fmtNum(ctx.kredit) + " so'm")}
    ${previewField('NPV', fmtNum(ind.npv) + " so'm")}
    ${previewField('IRR', (ind.irr || '—') + "%")}
    ${previewField('ROI', (ind.roi || '—') + "%")}
    ${previewField('PI', ind.pi || '—')}
    ${previewField("O'zini oqlash", ind.payback ? ind.payback + ' yil' : '—')}
  </div>`;

  // -- Jadvallar --
  for (const tbl of tables) {
    if (!tbl.headers.length || !tbl.rows.length) continue;
    html += `<div class="preview-section">
      <h3>${tbl.ilova} — ${tbl.title}</h3>
      <div class="preview-table-wrap">
        <table class="preview-table">
          <thead><tr>${tbl.headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
          <tbody>`;
    for (const row of tbl.rows) {
      const isTotal = row[0] && typeof row[0] === 'string' && (row[0].startsWith('JAMI') || row[0].startsWith('LOYIHA') || row[0].startsWith('SOF') || row[0].startsWith('YALPI') || row[0].startsWith('TANNARX') || row[0].startsWith('OPERATSION') || row[0].startsWith('KUMULYATIV'));
      html += `<tr${isTotal ? ' class="row-total"' : ''}>`;
      for (const cell of row) {
        const val = typeof cell === 'number' ? fmtNum(cell) : (cell === null || cell === '' ? '' : cell);
        html += `<td>${val}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table></div></div>';
  }

  container.innerHTML = html;
}

function previewField(label, value, editName) {
  const val = value || '—';
  if (editName) {
    return `<div class="preview-field">
      <span class="pf-label">${label}:</span>
      <input class="pf-value" type="text" data-field="${editName}" value="${val}" onchange="updatePreviewField('${editName}', this.value)">
    </div>`;
  }
  return `<div class="preview-field"><span class="pf-label">${label}:</span><span class="pf-value" style="cursor:default">${val}</span></div>`;
}

function updatePreviewField(field, value) {
  // Update form hidden input or main input
  const inp = document.querySelector(`[name="${field}"]`);
  if (inp) inp.value = value;
}

// ============================================================
// PAYMENT & DOWNLOAD
// ============================================================
function selectPayment(method) {
  selectedPaymentMethod = method;
  document.querySelectorAll('.payment-card').forEach(c => {
    c.classList.toggle('active', c.dataset.method === method);
  });
  const btn = document.getElementById('downloadBtn');
  if (method === 'demo') {
    btn.textContent = '🧪 Demo — Bepul yuklab olish';
  } else {
    btn.textContent = `📥 To'lash va yuklab olish — 80 000 so'm`;
  }
}

async function processPaymentAndDownload() {
  const btn = document.getElementById('downloadBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Jarayon ketmoqda...';

  try {
    // 1. To'lov yaratish
    const payResp = await fetch('/api/payment/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method: selectedPaymentMethod }),
    });
    const payJson = await payResp.json();
    if (!payJson.success) throw new Error(payJson.error || "To'lov yaratib bo'lmadi");

    const paymentId = payJson.payment.id;

    // 2. To'lovni tasdiqlash (demo da avtomatik)
    if (selectedPaymentMethod === 'demo') {
      const verResp = await fetch('/api/payment/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_id: paymentId }),
      });
      const verJson = await verResp.json();
      if (!verJson.success) throw new Error(verJson.error || "To'lov tasdiqlanmadi");
    } else {
      // Haqiqiy to'lov uchun - demo alert
      alert(`${selectedPaymentMethod.toUpperCase()} to'lov tizimi hozirda test rejimda ishlaydi.\nTo'lov ID: ${paymentId}\n\nDemo rejimda davom etamiz.`);
      const verResp = await fetch('/api/payment/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_id: paymentId }),
      });
      const verJson = await verResp.json();
      if (!verJson.success) throw new Error(verJson.error);
    }

    // 3. PDF yuklab olish
    btn.textContent = '📄 PDF yaratilmoqda...';
    
    const overlay = document.getElementById('loadingOverlay');
    const fill = document.getElementById('progressFill');
    const title = document.getElementById('loadingTitle');
    const text = document.getElementById('loadingText');

    overlay.classList.add('active');
    const steps = [
      {p:15, t:'Ma\'lumotlar saqlanmoqda...', x:'Excel faylga yozilmoqda'},
      {p:30, t:'Kredit jadvali...', x:'To\'lov jadvali yaratilmoqda'},
      {p:50, t:'Moliyaviy tahlil...', x:'NPV, IRR, ROI hisoblanmoqda'},
      {p:70, t:'Word yaratilmoqda...', x:'Shablon to\'ldirilmoqda'},
      {p:85, t:'PDF yaratilmoqda...', x:'Hujjat konvertatsiya qilinmoqda'},
      {p:95, t:'Yakunlanmoqda...', x:'PDF birlashtirish'}
    ];
    let si = 0;
    const pi = setInterval(() => {
      if (si < steps.length) { fill.style.width = steps[si].p+'%'; title.textContent = steps[si].t; text.textContent = steps[si].x; si++; }
    }, 1500);

    const fd = new FormData(document.getElementById('biznesForm'));
    const resp = await fetch('/save', { method: 'POST', body: fd });
    clearInterval(pi);

    if (resp.ok) {
      fill.style.width = '100%';
      title.textContent = 'Tayyor! ✅';
      text.textContent = 'PDF yuklab olinmoqda...';
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'biznes_reja.pdf';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setTimeout(() => overlay.classList.remove('active'), 1500);
    } else {
      overlay.classList.remove('active');
      const d = await resp.json();
      showAlert(d.errors ? d.errors.join('. ') : 'PDF yaratishda xatolik');
    }
  } catch (err) {
    showAlert(err.message || "Xatolik yuz berdi");
    document.getElementById('loadingOverlay')?.classList.remove('active');
  } finally {
    btn.disabled = false;
    if (selectedPaymentMethod === 'demo') {
      btn.textContent = '🧪 Demo — Bepul yuklab olish';
    } else {
      btn.textContent = `📥 To'lash va yuklab olish — 80 000 so'm`;
    }
  }
}

// ============================================================
// FORM SUBMIT (fallback)
// ============================================================
function setupFormSubmit() {
  document.getElementById('biznesForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    // Redirect to preview instead of direct submit
    generatePreview();
  });
}

// ============================================================
// HELPERS
// ============================================================
function fmt(n) {
  if (!n || n <= 0) return "0 so'm";
  return Math.round(n).toLocaleString('uz-UZ') + " so'm";
}
function fmtNum(n) {
  if (n === null || n === undefined || n === '') return '0';
  if (typeof n === 'string') return n;
  return Math.round(n).toLocaleString('uz-UZ');
}
function showAlert(msg) {
  const b = document.getElementById('alertBox');
  if (b) { b.textContent = msg; b.style.display = 'block'; b.scrollIntoView({behavior:'smooth',block:'center'}); }
}
function hideAlert() {
  const b = document.getElementById('alertBox');
  if (b) b.style.display = 'none';
}
