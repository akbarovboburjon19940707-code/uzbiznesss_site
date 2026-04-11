// ============================================================
// BIZNES REJA PLATFORMASI v2.0 — Enterprise Dashboard Logic
// Real-time Analytics | Dashboard UI | Smooth Transitions
// ============================================================
let currentStep = 1;
const totalSteps = 8;
let calcTimeout, analysisTimeout;
let categoriesData = null;
let allPlans = [];
let selectedFaoliyat = '';
let selectedPaymentMethod = 'demo';

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Kategoriyalarni yuklash
    await loadCategories();

    // 2. Navigatsiya (Stepper) setup
    setupStepper();

    // 3. Form inputlarini kuzatish (Real-time update)
    setupInputWatchers();

    // 4. Boshqa komponentlar
    setupAutocomplete();
    setupUploads();
    setupOrginfoFetcher();
    
    // Sidebar ni boshlang'ich holatda bo'shatish
    updateSidebarScorecard(null);
});

// ============================================================
// INITIALIZATION
// ============================================================
function setupOrginfoFetcher() {
    const stirInput = document.getElementById('stir_input');
    if (!stirInput) return;
    
    stirInput.addEventListener('input', async () => {
        const val = stirInput.value.trim();
        if (val.length === 9) {
            const loader = document.getElementById('org_loader');
            if (loader) loader.style.display = 'block';
            
            try {
                const resp = await fetch(`/api/orginfo/${val}`);
                const res = await resp.json();
                
                if (res.success && res.data) {
                    const d = res.data;
                    document.getElementById('tashabbuskor').value = d.tashabbuskor || '';
                    document.getElementById('fio_input').value = d.rahbar || '';
                    document.getElementById('manzil_input').value = d.manzil || '';
                    document.getElementById('bank_input').value = d.bank || '';
                    
                    const mulkSel = document.getElementById('mulk_select');
                    if (mulkSel && d.mulk) mulkSel.value = d.mulk;
                    
                    const soliqSel = document.getElementById('soliq_turi_select');
                    if (soliqSel && d.soliq_turi) soliqSel.value = d.soliq_turi;
                    
                    // Flash success effect
                    stirInput.style.borderColor = 'var(--accent)';
                    setTimeout(() => stirInput.style.borderColor = '', 1500);
                }
            } catch (e) {
                console.error("Orginfo fetch error:", e);
            } finally {
                if (loader) loader.style.display = 'none';
            }
        }
    });
}
async function loadCategories() {
    try {
        const resp = await fetch('/api/categories');
        const json = await resp.json();
        if (json.success) {
            categoriesData = json.data;
            allPlans = json.data.barcha_rejalar || [];
            console.log(`✅ ${allPlans.length} ta reja tayyor.`);
        }
    } catch (e) {
        console.warn('Data load error:', e);
    }
}

function setupStepper() {
    document.querySelectorAll('.step-bubble').forEach(bubble => {
        bubble.addEventListener('click', () => {
            const s = +bubble.dataset.step;
            if (s < currentStep) goToStep(s);
            else if (s === currentStep + 1) nextStep(s);
        });
    });
}

function setupInputWatchers() {
    // Har qanday input o'zgarganda xatolikni o'chirish
    document.querySelectorAll('input, select').forEach(inp => {
        inp.addEventListener('input', () => {
            inp.classList.remove('error');
            hideAlert();
        });
    });
}

// ============================================================
// NAVIGATION LOGIC
// ============================================================
function goToStep(s) {
    if (s < 1 || s > totalSteps) return;

    // 1. Step vizual almashinuvi
    document.querySelectorAll('.form-step').forEach(el => el.classList.remove('active'));
    const targetStep = document.getElementById('step' + s);
    if (targetStep) targetStep.classList.add('active');

    // 2. Stepper holatini yangilash
    document.querySelectorAll('.step-bubble').forEach(bubble => {
        const stepNum = +bubble.dataset.step;
        bubble.classList.remove('active', 'completed');
        if (stepNum === s) bubble.classList.add('active');
        else if (stepNum < s) bubble.classList.add('completed');
    });

    // 3. Progress bar yangilash (Scorecard dagi)
    const progress = (s / totalSteps) * 100;
    const bar = document.getElementById('scoreBar');
    if (bar) bar.style.width = progress + '%';

    // 4. Preview mode — Step 8 da light theme
    if (s === 8) {
        document.body.classList.add('preview-mode');
    } else {
        document.body.classList.remove('preview-mode');
    }

    currentStep = s;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function nextStep(s) {
    if (!validateStep(currentStep)) return;
    goToStep(s);
}

function prevStep(s) {
    goToStep(s);
}

function validateStep(stepNum) {
    const stepEl = document.getElementById('step' + stepNum);
    if (!stepEl) return true;

    const inputs = stepEl.querySelectorAll('input[required]');
    let ok = true;
    inputs.forEach(inp => {
        if (!inp.value.trim()) {
            inp.classList.add('error');
            ok = false;
        }
    });

    if (stepNum === 1 && !selectedFaoliyat) {
        showAlert("Iltimos, faoliyat turini tanlang");
        ok = false;
    }

    if (!ok && stepNum !== 8) showAlert("Majburiy maydonlarni to'ldiring");
    return ok;
}

// ============================================================
// AUTOCOMPLETE & FAOLIYAT
// ============================================================
function setupAutocomplete() {
    const input = document.getElementById('loyiha_nomi');
    const dropdown = document.getElementById('autocompleteDropdown');
    if (!input || !dropdown) return;

    let acHighlight = -1;      // Hozirgi tanlangan element indeksi
    let acResults = [];        // Hozirgi qidiruv natijalari
    let acDebounce = null;     // Debounce timer

    // ---- Dropdown ochish/yopish ----
    function openDropdown() {
        dropdown.classList.add('show');
    }

    function closeDropdown() {
        dropdown.classList.remove('show');
        acHighlight = -1;
        clearHighlight();
    }

    function clearHighlight() {
        dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
            el.classList.remove('ac-active');
        });
    }

    function setHighlight(index) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (items.length === 0) return;

        clearHighlight();
        acHighlight = Math.max(0, Math.min(index, items.length - 1));
        const active = items[acHighlight];
        active.classList.add('ac-active');

        // Scroll into view (agar ko'rinmasa)
        active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    // ---- Rendering ----
    function renderResults(query) {
        acResults = allPlans
            .filter(p => p.nomi.toLowerCase().includes(query))
            .slice(0, 20);

        acHighlight = -1;

        if (acResults.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-no-result">Natija topilmadi</div>';
        } else {
            dropdown.innerHTML = acResults.map((r, i) => `
                <div class="autocomplete-item" data-index="${i}">
                    <div class="ac-content">
                        <div class="ac-name">${highlightMatch(r.nomi, query)}</div>
                        <div class="ac-cat">${r.kategoriya || ''}</div>
                    </div>
                    <div class="ac-type-badge">${getTypeEmoji(r.faoliyat_turi)}</div>
                </div>
            `).join('');
        }
        openDropdown();
    }

    // Qidiruv so'zini highlight qilish
    function highlightMatch(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<mark class="ac-highlight">$1</mark>');
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function getTypeEmoji(type) {
        const map = {
            'ishlab_chiqarish': '🏭',
            'qishloq_xojaligi': '🌾',
            'savdo': '🏪',
            'xizmat': '🍽'
        };
        return map[type] || '';
    }

    // ---- Elementni tanlash ----
    function selectItem(index) {
        if (index < 0 || index >= acResults.length) return;
        const item = acResults[index];
        input.value = item.nomi;
        selectFaoliyat(item.faoliyat_turi);
        closeDropdown();
        input.blur(); // Fokusni olib tashlash (dropdown qayta ochilmasligi uchun)
    }

    // ---- INPUT hodisalari ----
    input.addEventListener('input', () => {
        clearTimeout(acDebounce);
        acDebounce = setTimeout(() => {
            const query = input.value.trim().toLowerCase();
            if (query.length < 2) {
                closeDropdown();
                return;
            }
            renderResults(query);
        }, 150); // 150ms debounce
    });

    // Fokus bo'lganda ham ochish (agar matn 2+ bo'lsa)
    input.addEventListener('focus', () => {
        const query = input.value.trim().toLowerCase();
        if (query.length >= 2 && acResults.length > 0) {
            openDropdown();
        }
    });

    // ---- KEYBOARD navigatsiya ----
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        const isOpen = dropdown.classList.contains('show');

        if (!isOpen) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setHighlight(acHighlight + 1);
                break;

            case 'ArrowUp':
                e.preventDefault();
                if (acHighlight <= 0) {
                    acHighlight = -1;
                    clearHighlight();
                } else {
                    setHighlight(acHighlight - 1);
                }
                break;

            case 'Enter':
                e.preventDefault();
                if (acHighlight >= 0 && acHighlight < items.length) {
                    selectItem(acHighlight);
                }
                break;

            case 'Escape':
                e.preventDefault();
                closeDropdown();
                break;

            case 'Tab':
                closeDropdown();
                break;
        }
    });

    // ---- CLICK: dropdown ichidagi elementni tanlash (Event Delegation) ----
    dropdown.addEventListener('mousedown', (e) => {
        // mousedown ishlatamiz (click emas), chunki blur dan oldin ishlaydi
        e.preventDefault(); // input.blur() ni to'xtatadi
        const item = e.target.closest('.autocomplete-item');
        if (item) {
            const index = parseInt(item.dataset.index, 10);
            selectItem(index);
        }
    });

    // ---- Hover bilan highlight ----
    dropdown.addEventListener('mousemove', (e) => {
        const item = e.target.closest('.autocomplete-item');
        if (item) {
            const index = parseInt(item.dataset.index, 10);
            if (index !== acHighlight) {
                setHighlight(index);
            }
        }
    });

    // ---- Tashqariga bosganda yopish ----
    document.addEventListener('mousedown', (e) => {
        if (!e.target.closest('#loyiha_nomi') && !e.target.closest('#autocompleteDropdown')) {
            closeDropdown();
        }
    });
}

function selectFaoliyat(type) {
    selectedFaoliyat = type;
    const hidden = document.getElementById('faoliyat_turi_hidden');
    if (hidden) hidden.value = type;

    document.querySelectorAll('.type-card').forEach(card => {
        card.classList.toggle('active', card.dataset.type === type);
    });

    updateStep4UI(type);
    updateAnalysis(); // Faoliyat turiga ko'ra marginlar o'zgaradi
}

function updateStep4UI(type) {
    if (!categoriesData) return;
    const ft = categoriesData.faoliyat_turlari[type];
    if (!ft) return;

    // Elementlarni yangilash
    const labels = {
        'mahsulotLabel': ft.mahsulot_label,
        'hajmLabel': ft.hajm_label,
        'narxLabel': ft.narx_label,
        'step4Title': ft.nomi + " Ma'lumotlari",
        'step4Desc': ft.tavsif
    };

    for (const [id, val] of Object.entries(labels)) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    // Dinamik qoshimcha fieldlar
    const container = document.getElementById('dynamicFields');
    if (container && ft.qoshimcha_fieldlar) {
        container.innerHTML = ft.qoshimcha_fieldlar.map(f => `
            <div class="input-box">
                <label>${f.label}</label>
                <input type="number" step="any" name="${f.name}" class="input-ctrl" placeholder="${f.placeholder || '0.00'}">
            </div>
        `).join('');
    }
}

// ============================================================
// CALCULATIONS & SCORECARD (SIDEBAR)
// ============================================================
function updateCalc() {
    clearTimeout(calcTimeout);
    calcTimeout = setTimeout(() => {
        const v = (id) => parseFloat(document.getElementById(id)?.value) || 0;
        const kredit = v('kredit_input');
        const foiz = v('foiz_input');
        const muddat = parseInt(document.getElementById('muddat_input')?.value) || 1;
        const imtiyoz = parseInt(document.getElementById('imtiyoz_input')?.value) || 0;
        
        const radioCards = document.querySelectorAll('input[name="kredit_turi"]');
        let turi = 'annuitet';
        radioCards.forEach(r => {
            const card = r.closest('.type-card');
            if (r.checked) {
                turi = r.value;
                if (card) card.classList.add('active');
            } else {
                if (card) card.classList.remove('active');
            }
        });

        if (kredit <= 0 || muddat <= 0) { renderQuickSchedule(null); return; }

        renderQuickSchedule({kredit, foiz, muddat, imtiyoz, turi});
    }, 250);
}

function renderQuickSchedule(params) {
    const wrap = document.getElementById('scheduleWrap');
    if (!wrap || !params) { if(wrap) wrap.innerHTML = ''; return; }

    const {kredit, foiz, muddat, imtiyoz, turi} = params;
    const r = foiz / 12 / 100;
    const asosiyMuddat = muddat - imtiyoz;
    
    let rows = '';
    let qoldiq = kredit;
    let limit = Math.min(muddat, 5); // Faqat 5 tasini ko'rsatamiz

    for (let i = 1; i <= limit; i++) {
        let tolov = 0, fTolov = qoldiq * r, aTolov = 0;
        if (i <= imtiyoz) {
            tolov = fTolov;
        } else {
            if (turi === 'annuitet') {
                tolov = kredit * (r * Math.pow(1+r, asosiyMuddat)) / (Math.pow(1+r, asosiyMuddat) - 1);
                aTolov = tolov - fTolov;
            } else {
                aTolov = kredit / asosiyMuddat;
                tolov = aTolov + fTolov;
            }
            qoldiq -= aTolov;
        }
        rows += `<tr><td>${i}-oy</td><td>${fmt(tolov)}</td><td>${fmt(aTolov)}</td><td>${fmt(fTolov)}</td><td>${fmt(qoldiq)}</td></tr>`;
    }

    wrap.innerHTML = `
        <table class="preview-table">
            <thead><tr><th>Davr</th><th>To'lov</th><th>Asosiy</th><th>Foiz</th><th>Qoldiq</th></tr></thead>
            <tbody>${rows}<tr><td colspan="5" style="text-align:center; font-style:italic; opacity:0.6; font-size:10px">... jami ${muddat} oy</td></tr></tbody>
        </table>
    `;
}

function updateAnalysis() {
    clearTimeout(analysisTimeout);
    analysisTimeout = setTimeout(() => {
        const v = (id) => parseFloat(document.getElementById(id)?.value) || 0;
        const loyiha = v('loyiha_qiymati');
        const hajm = v('hajm_input');
        const narx = v('narx_input');
        const revenue = hajm * narx;

        if (loyiha <= 0 || revenue <= 0) { updateSidebarScorecard(null); return; }

        // Rough calculation for real-time feedback
        let margin = 0.25;
        if (selectedFaoliyat === 'ishlab_chiqarish') margin = 0.22;
        else if (selectedFaoliyat === 'qishloq_xojaligi') margin = 0.35;
        else if (selectedFaoliyat === 'savdo') margin = 0.15;
        else if (selectedFaoliyat === 'xizmat') margin = 0.45;

        const yearlyProfit = revenue * margin;
        const roi = (yearlyProfit / loyiha) * 100;
        const payback = loyiha / yearlyProfit;
        const npv = (yearlyProfit * 5) - loyiha; // Simplified 5-year projection

        updateSidebarScorecard({npv, roi, payback, revenue});
    }, 400);
}

function updateSidebarScorecard(data) {
    const ids = {
        'sidebarNpv': data ? fmt(data.npv) : '—',
        'sidebarRoi': data ? data.roi.toFixed(1) + '%' : '—',
        'sidebarPayback': data ? data.payback.toFixed(1) + ' yil' : '—',
        'sidebarRevenue': data ? fmt(data.revenue) : '—'
    };

    for (const [id, val] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (el) {
            const valSpan = el.querySelector('.m-value');
            if (valSpan) {
                valSpan.textContent = val;
                // Positive/Negative coloring
                if (id === 'sidebarNpv') {
                    el.classList.toggle('positive', data && data.npv > 0);
                    el.classList.toggle('negative', data && data.npv <= 0);
                }
            }
        }
    }
}

// ============================================================
// PREVIEW & PAYMENT
// ============================================================
async function generatePreview() {
    if (!validateStep(currentStep)) return;
    
    goToStep(8);
    const container = document.getElementById('previewContent');
    container.innerHTML = '<div style="text-align:center; padding:40px"><div class="spinner"></div><p style="margin-top:15px; opacity:0.6">AI Analitika o\'tkazilmoqda...</p></div>';

    try {
        const formData = {};
        const form = document.getElementById('biznesForm');
        new FormData(form).forEach((v, k) => { if(typeof v === 'string' && k !== 'csrf_token') formData[k] = v; });

        const resp = await fetch('/api/preview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(formData)
        });
        const res = await resp.json();

        if (res.success) {
            renderPreviewUI(res.data, container);
            document.getElementById('paymentSection').classList.remove('hidden');
        } else {
            container.innerHTML = `<div style="color:var(--error); text-align:center">${res.error}</div>`;
        }
    } catch(e) {
        container.innerHTML = "Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.";
    }
}

function renderPreviewUI(data, container) {
    const ctx = data.context;
    const ind = data.indicators;
    const npvPositive = ind.npv > 0;
    const roiPositive = ind.roi > 0;

    // Format helpers
    const fmtNum = (n) => {
        if (n === null || n === undefined || isNaN(n)) return '0';
        return Math.round(n).toLocaleString('uz-UZ');
    };

    let html = `
    <div class="doc-preview">
      <div class="doc-page">

        <!-- Document Header -->
        <div class="doc-header">
          <div class="doc-header-top">
            <div class="doc-badge">
              <span class="doc-badge-icon"></span>
              Biznes Reja
            </div>
            <div class="doc-status">
              <span class="doc-status-dot"></span>
              Tahlil yakunlandi
            </div>
          </div>
          <h1 class="doc-title">${ctx.loyiha_nomi || 'Biznes loyiha'}</h1>
          <p class="doc-subtitle">${ctx.tashabbuskor || ''} &mdash; ${ctx.yil || new Date().getFullYear()}-yil</p>
        </div>

        <!-- Loyiha Pasporti -->
        <div class="doc-meta-section">
          <div class="doc-meta-label">Loyiha pasporti</div>
          <div class="doc-meta-grid">
            <div class="doc-meta-item">
              <span class="doc-meta-key">Loyiha nomi</span>
              <span class="doc-meta-val">${ctx.loyiha_nomi || '—'}</span>
            </div>
            <div class="doc-meta-item">
              <span class="doc-meta-key">Tashabbuskor</span>
              <span class="doc-meta-val">${ctx.tashabbuskor || '—'}</span>
            </div>
            <div class="doc-meta-item">
              <span class="doc-meta-key">Loyiha qiymati</span>
              <span class="doc-meta-val">${fmtNum(ctx.loyiha_qiymati)} so'm</span>
            </div>
            <div class="doc-meta-item">
              <span class="doc-meta-key">O'z mablag'i</span>
              <span class="doc-meta-val">${fmtNum(ctx.oz_mablag)} so'm</span>
            </div>
            <div class="doc-meta-item">
              <span class="doc-meta-key">Kredit summasi</span>
              <span class="doc-meta-val">${fmtNum(ctx.kredit)} so'm</span>
            </div>
            <div class="doc-meta-item">
              <span class="doc-meta-key">Faoliyat turi</span>
              <span class="doc-meta-val">${data.faoliyat_nomi || ctx.faoliyat_turi || '—'}</span>
            </div>
          </div>
        </div>

        <!-- KPI ko'rsatkichlari -->
        <div class="doc-kpi-section">
          <div class="doc-meta-label">Moliyaviy ko'rsatkichlar</div>
          <div class="doc-kpi-grid">
            <div class="doc-kpi-card ${npvPositive ? 'positive' : 'negative'}">
              <div class="doc-kpi-label">NPV (Sof daromad)</div>
              <div class="doc-kpi-value">${fmtNum(ind.npv)}</div>
              <div class="doc-kpi-sub">so'm</div>
            </div>
            <div class="doc-kpi-card ${roiPositive ? 'positive' : 'negative'}">
              <div class="doc-kpi-label">ROI (Rentabellik)</div>
              <div class="doc-kpi-value">${(ind.roi || 0).toFixed(1)}%</div>
              <div class="doc-kpi-sub">${roiPositive ? 'Samarali' : 'Samarasiz'}</div>
            </div>
            <div class="doc-kpi-card ${npvPositive ? 'positive' : ''}">
              <div class="doc-kpi-label">IRR</div>
              <div class="doc-kpi-value">${ind.irr ? (ind.irr).toFixed(1) + '%' : '—'}</div>
              <div class="doc-kpi-sub">Ichki daromadlilik</div>
            </div>
          </div>
        </div>

        <!-- Moliyaviy jadvallar -->
        <div class="doc-tables-section">
          <div class="doc-meta-label">Moliyaviy jadvallar</div>
    `;

    // Professional Document Tables
    data.tables.forEach((tbl, idx) => {
        html += `
          <div class="doc-table-block" style="--table-index: ${idx}">
            <div class="doc-table-header">
              <span class="doc-table-badge">${tbl.ilova}</span>
              <span class="doc-table-name">${tbl.title}</span>
            </div>
            <div class="doc-table-wrap" style="max-height: 400px; overflow-y: auto">
              <table class="doc-table">
                <thead><tr>${tbl.headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
                <tbody>${tbl.rows.slice(0, 15).map(row =>
                    `<tr>${row.map(c => `<td>${typeof c === 'number' ? fmtNum(c) : c}</td>`).join('')}</tr>`
                ).join('')}</tbody>
              </table>
            </div>
          </div>
        `;
    });

    html += `
        </div>

        <!-- Footer Note -->
        <div class="doc-footer-note">
          <p class="doc-footer-text">
            <strong>Barcha 12+ professional moliyaviy jadvallar</strong> yuklab olinganda to'liq holatda 
            (har bir oy/yil kesimida) taqdim etiladi. Ushbu hujjat avtomatik generatsiya qilingan.
          </p>
        </div>

      </div>
    </div>
    `;

    container.innerHTML = html;

    // Animate tables sequentially
    requestAnimationFrame(() => {
        document.querySelectorAll('.doc-table-block').forEach(el => {
            el.style.opacity = '1';
        });
    });
}

// ============================================================
// UPLOADS & UTILS
// ============================================================
function setupUploads() {
    // Basic file display
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', () => {
            if (input.files.length) {
                console.log(`File: ${input.files[0].name}`);
            }
        });
    });
}

function selectPayment(method) {
    selectedPaymentMethod = method;
    document.querySelectorAll('#paymentMethods .type-card').forEach(c => {
        c.classList.toggle('active', c.dataset.method === method);
    });
}

function fmt(n) {
    if (n === null || n === undefined || isNaN(n)) return "0";
    if (Math.abs(n) > 1000) {
        return Math.round(n).toLocaleString('uz-UZ') + " so'm";
    }
    return n.toLocaleString('uz-UZ');
}

function showAlert(msg) {
    const box = document.getElementById('alertBox');
    if (box) {
        box.textContent = msg;
        box.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function hideAlert() {
    document.getElementById('alertBox')?.classList.add('hidden');
}

// Payment/Download glue (Reuse backend call logic)
async function processPaymentAndDownload(format = 'pdf') {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');
    
    try {
        const form = document.getElementById('biznesForm');
        const fd = new FormData(form);
        fd.append('format', format);

        const resp = await fetch('/save', { method: 'POST', body: fd });
        
        if (resp.ok) {
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; 
            
            // Professional fayl nomini serverdan olish
            let filename = null;
            const disposition = resp.headers.get('Content-Disposition');
            if (disposition) {
                // filename*=UTF-8''encoded_name yoki filename="name" formatlarini qidirish
                const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
                const plainMatch = disposition.match(/filename="?([^"\n;]+)"?/i);
                if (utf8Match) filename = decodeURIComponent(utf8Match[1]);
                else if (plainMatch) filename = plainMatch[1].trim();
            }
            
            // Fallback: Content-Type dan aniqlash
            if (!filename) {
                const contentType = resp.headers.get('Content-Type');
                const isWord = contentType && contentType.includes('wordprocessingml');
                filename = isWord ? 'biznes_reja.docx' : 'biznes_reja.pdf';
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            setTimeout(() => overlay.classList.remove('active'), 1000);
        } else {
            const res = await resp.json();
            overlay.classList.remove('active');
            showAlert(res.errors ? res.errors[0] : "Xatolik yuz berdi");
        }
    } catch(e) {
        overlay.classList.remove('active');
        showAlert("Server bilan aloqa uzildi");
    }
}
