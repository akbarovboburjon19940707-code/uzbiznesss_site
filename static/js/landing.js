/* ============================================================
   UzBizness Landing Page — JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ── Header Scroll Effect ──
    const header = document.getElementById('siteHeader');
    const handleScroll = () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });

    // ── Mobile Menu Toggle ──
    const mobileToggle = document.getElementById('mobileToggle');
    const mainNav = document.getElementById('mainNav');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            mobileToggle.classList.toggle('active');
            mainNav.classList.toggle('open');
        });
    }

    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            mobileToggle.classList.remove('active');
            mainNav.classList.remove('open');
        });
    });

    // ── Active nav link on scroll ──
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');

    const observerOptions = {
        root: null,
        rootMargin: '-80px 0px -40% 0px',
        threshold: 0
    };

    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }, observerOptions);

    sections.forEach(section => sectionObserver.observe(section));

    // ── Counter Animation ──
    const counters = document.querySelectorAll('.stat-number[data-count]');

    const animateCounter = (el) => {
        const target = parseInt(el.getAttribute('data-count'));
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;

        const updateCounter = () => {
            current += step;
            if (current >= target) {
                el.textContent = target.toLocaleString();
                return;
            }
            el.textContent = Math.floor(current).toLocaleString();
            requestAnimationFrame(updateCounter);
        };

        updateCounter();
    };

    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => counterObserver.observe(counter));

    // ── Scroll Reveal Animations ──
    const revealElements = document.querySelectorAll(
        '.knowledge-card, .step-card, .feature-card, .pricing-card, .blog-card, .section-header'
    );

    revealElements.forEach(el => el.classList.add('reveal'));

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Stagger the animation
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 80);
                revealObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));

    // ── Back to Top Button ──
    const backToTop = document.getElementById('backToTop');

    const checkBackToTop = () => {
        if (window.scrollY > 500) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
    };

    window.addEventListener('scroll', checkBackToTop, { passive: true });

    if (backToTop) {
        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // ── Smooth scroll for anchor links ──
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // ── Parallax effect on hero shapes ──
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const scrolled = window.scrollY;
                const shapes = document.querySelectorAll('.hero-shape');
                shapes.forEach((shape, i) => {
                    const speed = (i + 1) * 0.05;
                    shape.style.transform = `translateY(${scrolled * speed}px)`;
                });
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });

    // ── Typing effect for hero badge (subtle) ──
    const heroImage = document.querySelector('.hero-image');
    if (heroImage) {
        heroImage.addEventListener('load', () => {
            heroImage.style.opacity = '1';
        });
    }

    // ── Card hover tilt effect ──
    const tiltCards = document.querySelectorAll('.knowledge-card, .feature-card, .pricing-card');

    tiltCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / centerY * -3;
            const rotateY = (x - centerX) / centerX * 3;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });

    // ── Pricing card popular hover fix ──
    const popularCard = document.querySelector('.pricing-card-popular');
    if (popularCard) {
        popularCard.addEventListener('mousemove', (e) => {
            const rect = popularCard.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / centerY * -2;
            const rotateY = (x - centerX) / centerX * 2;

            popularCard.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05) translateY(-8px)`;
        });

        popularCard.addEventListener('mouseleave', () => {
            popularCard.style.transform = 'scale(1.05)';
        });
    }

    // ── Load Catalog Products ──
    loadCatalogProducts();

    console.log('🚀 UzBizness Landing Page loaded successfully');
});


/* ============================================================
   CATALOG MARKETPLACE — JavaScript
   ============================================================ */

// State
let _catalogProducts = [];
let _currentProductId = null;
let _currentPayMethod = 'click';
let _currentPaymentId = null;
let _pollTimer = null;

// Lazy Loading State
let _currentCategory = null;
let _currentPage = 1;
let _hasMoreProducts = false;
let _categoryCache = {};
let _loadingProducts = false;
let _allProductsMap = {};  // Barcha yuklangan mahsulotlar xaritasi (ID -> product)

/* ============================================================
   CATALOG LAZY LOADING — Kategoriya bo'yicha yuklash
   ============================================================ */

/**
 * Kategoriyalarni API dan yuklash va tablar yaratish
 */
async function loadCatalogProducts() {
    const tabsContainer = document.getElementById('catalogTabsContainer');
    if (!tabsContainer) return;

    try {
        const resp = await fetch('/api/catalog/categories');
        const data = await resp.json();

        if (!data.success || !data.categories || data.categories.length === 0) {
            tabsContainer.innerHTML = '<p style="color:var(--gray-400);font-size:14px;">Bo\'limlar topilmadi</p>';
            return;
        }

        // Tab tugmalar yaratish
        tabsContainer.innerHTML = '';
        data.categories.forEach((cat, index) => {
            const btn = document.createElement('button');
            btn.className = 'catalog-tab-btn' + (index === 0 ? ' active' : '');
            btn.dataset.key = cat.key;
            btn.innerHTML = `
                <span class="ctb-icon">${cat.icon}</span>
                <span class="ctb-label">${cat.label}</span>
                <span class="ctb-count">${cat.count}</span>
            `;
            btn.onclick = () => selectCatalogCategory(cat.key);
            tabsContainer.appendChild(btn);
        });

        // Birinchi kategoriyani avtomatik yuklash
        if (data.categories.length > 0) {
            selectCatalogCategory(data.categories[0].key);
        }

    } catch (err) {
        console.error('Kategoriyalar yuklanmadi:', err);
        tabsContainer.innerHTML = '<p style="color:var(--gray-400);">Yuklanmadi</p>';
    }
}


/**
 * Kategoriyani tanlash va mahsulotlarni yuklash (lazy loading)
 */
async function selectCatalogCategory(folderKey) {
    const container = document.getElementById('catalogContainer');
    if (_currentCategory === folderKey && container && container.children.length > 0 && !container.querySelector('.catalog-empty')) {
        return;
    }
    _currentCategory = folderKey;
    _currentPage = 1;
    _hasMoreProducts = false;

    // Active tab ni o'zgartirish
    document.querySelectorAll('.catalog-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.key === folderKey);
    });

    if (!container) return;

    // Kesh tekshirish
    const cacheKey = `${folderKey}_1`;
    if (_categoryCache[cacheKey]) {
        const cached = _categoryCache[cacheKey];
        _catalogProducts = cached.products || [];
        (cached.products || []).forEach(p => { _allProductsMap[p.id] = p; });
        renderCatalogProducts(cached.products, false);
        _hasMoreProducts = cached.has_more;
        updateLoadMoreBtn();
        return;
    }

    // Loading ko'rsatish
    container.innerHTML = `
        <div class="catalog-empty" style="padding: 60px 0;">
            <div class="status-spinner" style="width:36px;height:36px;border:3px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 14px;"></div>
            <p style="color:var(--gray-400);font-size:14px;">Yuklanmoqda...</p>
        </div>`;

    await fetchAndRenderCategory(folderKey, 1, false);
}


/**
 * API dan kategoriya mahsulotlarini yuklash
 */
async function fetchAndRenderCategory(folderKey, page, append) {
    if (_loadingProducts) return;
    _loadingProducts = true;

    try {
        const resp = await fetch(`/api/catalog/by-category/${folderKey}?page=${page}&per_page=20`);
        const data = await resp.json();

        if (!data.success) {
            if (!append) {
                document.getElementById('catalogContainer').innerHTML =
                    '<div class="catalog-empty"><p>Mahsulotlar topilmadi</p></div>';
            }
            return;
        }

        // Keshga saqlash
        _categoryCache[`${folderKey}_${page}`] = data;

        // Barcha mahsulotlarni xaritaga saqlash
        (data.products || []).forEach(p => { _allProductsMap[p.id] = p; });

        // _catalogProducts ni yangilash (modal uchun)
        if (append) {
            _catalogProducts = _catalogProducts.concat(data.products || []);
        } else {
            _catalogProducts = data.products || [];
        }

        _hasMoreProducts = data.has_more;
        _currentPage = page;

        renderCatalogProducts(data.products, append);
        updateLoadMoreBtn();

    } catch (err) {
        console.error('Mahsulotlar yuklanmadi:', err);
        if (!append) {
            document.getElementById('catalogContainer').innerHTML =
                '<div class="catalog-empty"><p>Yuklanishda xatolik</p></div>';
        }
    } finally {
        _loadingProducts = false;
    }
}


/**
 * Mahsulot kartochkalarini DOM ga joylashtirish
 */
function renderCatalogProducts(products, append) {
    const container = document.getElementById('catalogContainer');
    if (!container) return;

    if (!products || products.length === 0) {
        if (!append) {
            container.innerHTML = `
                <div class="catalog-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <p>Bu bo'limda hozircha mahsulot yo'q</p>
                </div>`;
        }
        return;
    }

    let grid;
    if (append) {
        grid = container.querySelector('.catalog-grid-new');
        if (!grid) {
            grid = document.createElement('div');
            grid.className = 'catalog-grid-new';
            container.appendChild(grid);
        }
    } else {
        container.innerHTML = '';
        grid = document.createElement('div');
        grid.className = 'catalog-grid-new';
        container.appendChild(grid);
    }

    products.forEach(product => {
        const card = document.createElement('div');
        card.className = 'catalog-item-card';
        card.dataset.id = product.id;
        card.onclick = () => openProductDetailModal(product.id);

        const ext = product.file_extension || '.pdf';
        const size = product.file_size_formatted || '3.44 MB';
        const views = (product.views_count !== undefined && product.views_count !== null) ? product.views_count : 0;
        const downloads = product.download_count || 0;

        card.innerHTML = `
            <div class="ci-header">
                <span class="ci-badge">${ext}</span>
                <div class="ci-actions">
                    <button class="ci-btn-icon" onclick="event.stopPropagation();"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg></button>
                    <button class="ci-btn-icon" onclick="event.stopPropagation(); openProductDetailModal('${product.id}');"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg></button>
                </div>
            </div>
            <div class="ci-image">
                <img src="${product.preview_image || '/static/img/placeholder.png'}" alt="${product.title}" loading="lazy">
            </div>
            <div class="ci-content">
                <h4 class="ci-title" title="${product.title}">${product.title}</h4>
                <div class="ci-price">${product.price_formatted}</div>
            </div>
            <div class="ci-footer">
                <div class="ci-stat"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg> ${size}</div>
                <div class="ci-stat" title="Yuklab olishlar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> ${downloads}</div>
                <div class="ci-stat" title="Ko'rishlar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> <span class="ci-stat-views">${views}</span></div>
            </div>
        `;
        grid.appendChild(card);
    });
}


/**
 * "Ko'proq yuklash" tugmasini yangilash
 */
function updateLoadMoreBtn() {
    const wrap = document.getElementById('catalogLoadMoreWrap');
    if (wrap) wrap.style.display = _hasMoreProducts ? 'block' : 'none';
}


/**
 * Ko'proq mahsulot yuklash (pagination)
 */
async function loadMoreCatalogProducts() {
    if (!_currentCategory || _loadingProducts || !_hasMoreProducts) return;
    const nextPage = _currentPage + 1;
    const btn = document.getElementById('catalogLoadMoreBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Yuklanmoqda...'; }
    await fetchAndRenderCategory(_currentCategory, nextPage, true);
    if (btn) { btn.disabled = false; btn.textContent = "Ko'proq ko'rish"; }
}


/**
 * Yagona Product Detail Modalini ochish (xavfsiz va kafolatlangan)
 */
async function openProductDetailModal(productId) {
    console.log('[MODAL] Ochilmoqda, product_id:', productId);
    _currentProductId = productId;

    // Ko'rishlar hisoblagichini serverda va UI da darhol oshirish
    fetch(`/api/catalog/view/${productId}`, { method: 'POST' }).catch(() => {});
    document.querySelectorAll(`.catalog-item-card[data-id="${productId}"] .ci-stat-views`).forEach(el => {
        const cur = parseInt(el.textContent.trim()) || 0;
        el.textContent = cur + 1;
    });
    if (_allProductsMap[productId]) {
        _allProductsMap[productId].views_count = (_allProductsMap[productId].views_count || 0) + 1;
    }

    // 1. Avval xaritadan yoki massivdan qidiramiz
    let product = _allProductsMap[productId] || _catalogProducts.find(p => String(p.id) === String(productId));

    // 2. Keshdan qidiramiz
    if (!product) {
        for (const k in _categoryCache) {
            const list = _categoryCache[k]?.products || [];
            const found = list.find(p => String(p.id) === String(productId));
            if (found) { product = found; _allProductsMap[productId] = found; break; }
        }
    }

    // 3. Agar hali ham topilmasa, API dan yuklab olamiz
    if (!product) {
        try {
            const resp = await fetch(`/api/catalog/product/${productId}`);
            const data = await resp.json();
            if (data.success && data.product) {
                product = data.product;
                _allProductsMap[productId] = product;
            }
        } catch (e) {
            console.error('[MODAL] Mahsulotni yuklashda xatolik:', e);
        }
    }

    if (!product) {
        console.error('[MODAL] Mahsulot topilmadi:', productId);
        return;
    }

    // Modal overlay ni darhol ochish
    const overlay = document.getElementById('productDetailModalOverlay');
    if (!overlay) {
        console.error('[MODAL] productDetailModalOverlay elementi topilmadi!');
        return;
    }

    // Reset payment form steps
    const step1 = document.getElementById('purchaseStep1');
    const step2 = document.getElementById('purchaseStep2');
    const step3 = document.getElementById('purchaseStep3');
    if (step1) step1.style.display = '';
    if (step2) step2.style.display = 'none';
    if (step3) step3.style.display = 'none';

    // Set product info in payment column
    const nameEl = document.getElementById('purchaseProductName');
    const priceEl = document.getElementById('purchasePrice');
    if (nameEl) nameEl.textContent = product.title || 'Biznes reja';
    if (priceEl) priceEl.textContent = product.price_formatted || `${product.price || 30000} so'm`;

    // Reset form inputs
    const userInp = document.getElementById('catalogUserName');
    if (userInp) userInp.value = '';
    const cardPan = document.getElementById('catalogCardPanel');
    if (cardPan) cardPan.style.display = 'none';
    selectCatalogPayMethod('click');

    // Reset preview column
    const prevTitle = document.getElementById('previewTitle');
    if (prevTitle) prevTitle.textContent = product.title || 'Hujjat namunasi';
    const prevInfo = document.getElementById('previewPagesInfo');
    if (prevInfo) prevInfo.textContent = '';
    const prevBody = document.getElementById('previewModalBody');
    if (prevBody) {
        prevBody.innerHTML = `
            <div class="preview-loading">
                <div class="status-spinner"></div>
                <p>Sahifalar yuklanmoqda...</p>
            </div>`;
    }

    // Show modal overlay
    overlay.classList.add('active');
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // API dan preview sahifalarini yuklash
    loadPreviewPages(productId);
}

function closeProductDetailModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const overlay = document.getElementById('productDetailModalOverlay');
    if (overlay) {
        overlay.classList.remove('active');
        overlay.style.display = 'none';
    }
    document.body.style.overflow = '';
    if (_pollTimer) clearInterval(_pollTimer);
}

async function loadPreviewPages(productId) {
    const body = document.getElementById('previewModalBody');

    try {
        const resp = await fetch(`/api/catalog/preview/${productId}`);
        const data = await resp.json();

        if (!data.success) {
            body.innerHTML = `<div class="preview-loading"><p>Preview yuklanmadi: ${data.error || 'Noma\'lum xatolik'}</p></div>`;
            return;
        }

        if (data.preview_type === 'image_only' || data.pages.length === 0) {
            // Faqat rasm ko'rsatish
            const product = _catalogProducts.find(p => p.id === productId);
            body.innerHTML = `
                <div class="preview-page-item">
                    <img class="preview-page-img" src="${product?.preview_image || ''}" alt="Preview">
                    <span class="preview-page-label">Muqova</span>
                </div>
                <div class="preview-loading" style="padding:30px;">
                    <p>Hujjatning to'liq ko'rinishini sotib olganingizdan keyin ko'rishingiz mumkin.</p>
                </div>`;
            return;
        }

        document.getElementById('previewPagesInfo').textContent =
            `${data.pages.length} ta sahifa / jami ${data.total_pages} sahifa`;

        let html = '';
        let prevPageNum = 0;

        data.pages.forEach((page, index) => {
            if (prevPageNum > 0 && page.page_number - prevPageNum > 1) {
                html += `<div class="preview-page-separator">• • •</div>`;
            }

            html += `
                <div class="preview-page-item">
                    <img class="preview-page-img" src="${page.image_url}" alt="Sahifa ${page.page_number}" loading="lazy">
                    <span class="preview-page-label">${page.page_number}-sahifa</span>
                </div>`;

            prevPageNum = page.page_number;
        });

        body.innerHTML = html;

    } catch (err) {
        console.error('Preview xatolik:', err);
        body.innerHTML = `<div class="preview-loading"><p>Preview yuklanmadi</p></div>`;
    }
}

/**
 * To'lov usulini tanlash
 */
function selectCatalogPayMethod(method) {
    _currentPayMethod = method;

    // Tabs
    document.querySelectorAll('.catalog-pay-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.method === method);
    });

    // Card panel
    const cardPanel = document.getElementById('catalogCardPanel');
    cardPanel.style.display = method === 'card' ? '' : 'none';

    // Button text
    const btnTexts = {
        'click': 'Click orqali to\'lash',
        'payme': 'Payme orqali to\'lash',
        'card': 'To\'lovni yuborish'
    };
    document.getElementById('catalogPayBtnText').textContent = btnTexts[method] || 'To\'lash';
}

/**
 * To'lovni yuborish
 */
async function submitCatalogPayment() {
    const userName = document.getElementById('catalogUserName').value.trim();
    if (!userName) {
        alert('Iltimos, ismingizni kiriting');
        document.getElementById('catalogUserName').focus();
        return;
    }

    const btn = document.getElementById('catalogPayBtn');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Yuklanmoqda...';

    try {
        if (_currentPayMethod === 'card') {
            const receiptFile = document.getElementById('catalogReceiptFile').files[0];
            if (!receiptFile) {
                alert('Iltimos, to\'lov chekini yuklang');
                btn.disabled = false;
                btn.querySelector('span').textContent = 'To\'lovni yuborish';
                return;
            }

            // 1. To'lov yaratish
            const resp = await fetch('/api/catalog/purchase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: _currentProductId,
                    payment_method: 'card',
                    user_name: userName
                })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'To\'lov yaratishda xatolik');

            _currentPaymentId = data.payment_id;

            // 2. Receipt yuklash
            const formData = new FormData();
            formData.append('receipt', receiptFile);
            formData.append('user_name', userName);
            formData.append('loyiha_nomi', 'Tayyor biznes reja');

            const submitResp = await fetch('/api/payment/submit', {
                method: 'POST',
                body: formData
            });

            // 3. Polling boshlash
            showPurchaseStep(2);
            document.getElementById('catalogStatusTitle').textContent = 'To\'lovingiz tekshirilmoqda...';
            document.getElementById('catalogStatusDesc').textContent = 'Admin chekingizni tekshiradi va tasdiqlaydi.';
            startCatalogPolling(_currentPaymentId);

        } else {
            // Click / Payme
            const resp = await fetch('/api/catalog/purchase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: _currentProductId,
                    payment_method: _currentPayMethod,
                    user_name: userName
                })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'To\'lov yaratishda xatolik');

            _currentPaymentId = data.payment_id;

            if (data.payment_url) {
                showPurchaseStep(2);
                document.getElementById('catalogStatusTitle').textContent =
                    _currentPayMethod === 'click' ? 'Click sahifasiga yo\'naltirilmoqda...' : 'Payme sahifasiga yo\'naltirilmoqda...';
                document.getElementById('catalogStatusDesc').textContent = 'To\'lovdan keyin avtomatik tasdiqlanadi.';

                startCatalogPolling(_currentPaymentId);

                setTimeout(() => {
                    window.open(data.payment_url, '_blank');
                }, 500);
            }
        }

    } catch (err) {
        console.error('To\'lov xatolik:', err);
        if (typeof window.showAlert === 'function') {
            window.showAlert('Xatolik: ' + err.message);
        } else {
            alert('Xatolik: ' + err.message);
        }
    } finally {
        btn.disabled = false;
        selectCatalogPayMethod(_currentPayMethod);
    }
}

/**
 * To'lov holatini polling qilish
 */
function startCatalogPolling(paymentId) {
    if (_pollTimer) clearInterval(_pollTimer);

    let attempts = 0;
    const maxAttempts = 300; // 5 daqiqa

    _pollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(_pollTimer);
            document.getElementById('catalogStatusTitle').textContent = 'Vaqt tugadi';
            document.getElementById('catalogStatusDesc').textContent = 'Iltimos, qaytadan urinib ko\'ring.';
            return;
        }

        try {
            const resp = await fetch(`/api/payment/status/${paymentId}`);
            const data = await resp.json();

            if (data.success) {
                if (data.status === 'approved') {
                    clearInterval(_pollTimer);
                    showPurchaseStep(3);
                    document.getElementById('catalogDownloadLink').href =
                        `/api/catalog/download/${paymentId}`;
                } else if (data.status === 'rejected') {
                    clearInterval(_pollTimer);
                    document.getElementById('catalogStatusTitle').textContent = 'To\'lov rad etildi';
                    document.getElementById('catalogStatusDesc').textContent =
                        data.admin_note || 'Admin to\'lovni rad etdi. Qaytadan urinib ko\'ring.';
                }
            }
        } catch (err) {
            console.error('Polling xatolik:', err);
        }
    }, 1000);
}

function showPurchaseStep(step) {
    document.getElementById('purchaseStep1').style.display = step === 1 ? '' : 'none';
    document.getElementById('purchaseStep2').style.display = step === 2 ? '' : 'none';
    document.getElementById('purchaseStep3').style.display = step === 3 ? '' : 'none';
}
