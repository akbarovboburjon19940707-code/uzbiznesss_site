/* ============================================================
   Payment Page — JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    const receiptFile = document.getElementById('receiptFile');
    const uploadZone = document.getElementById('uploadZone');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const uploadPreview = document.getElementById('uploadPreview');
    const previewImg = document.getElementById('previewImg');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const btnRemoveFile = document.getElementById('btnRemoveFile');
    const btnSubmitPayment = document.getElementById('btnSubmitPayment');
    const btnCopyCard = document.getElementById('btnCopyCard');
    const copyText = document.getElementById('copyText');
    const payUserName = document.getElementById('payUserName');

    let selectedFile = null;
    let currentPaymentId = null;
    let pollTimer = null;

    // URL dan payment_id olish
    const params = new URLSearchParams(window.location.search);
    const existingPaymentId = params.get('payment_id');
    if (existingPaymentId) {
        currentPaymentId = existingPaymentId;
        checkPaymentStatus();
    }


    // ── 1. Copy Card Number ──
    btnCopyCard.addEventListener('click', () => {
        const cardNum = '9860040102031362';
        navigator.clipboard.writeText(cardNum).then(() => {
            copyText.textContent = 'Nusxalandi!';
            btnCopyCard.classList.add('copied');
            setTimeout(() => {
                copyText.textContent = 'Nusxalash';
                btnCopyCard.classList.remove('copied');
            }, 2000);
        }).catch(() => {
            // Fallback
            const ta = document.createElement('textarea');
            ta.value = cardNum;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            copyText.textContent = 'Nusxalandi!';
            btnCopyCard.classList.add('copied');
            setTimeout(() => {
                copyText.textContent = 'Nusxalash';
                btnCopyCard.classList.remove('copied');
            }, 2000);
        });
    });


    // ── 2. File Upload ──
    receiptFile.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        handleFile(file);
    });

    // Drag & Drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    function handleFile(file) {
        const maxSize = 10 * 1024 * 1024;
        const allowed = ['image/jpeg', 'image/png', 'application/pdf'];

        if (!allowed.includes(file.type)) {
            alert('Faqat JPG, PNG yoki PDF fayl yuklang');
            return;
        }
        if (file.size > maxSize) {
            alert('Fayl 10MB dan katta');
            return;
        }

        selectedFile = file;
        uploadPlaceholder.classList.add('hidden');
        uploadPreview.classList.remove('hidden');
        uploadZone.classList.add('has-file');

        fileName.textContent = file.name;
        fileSize.textContent = formatSize(file.size);

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => { previewImg.src = e.target.result; };
            reader.readAsDataURL(file);
            previewImg.style.display = 'block';
        } else {
            previewImg.style.display = 'none';
        }

        updateSubmitState();
        updateSidebar('receipt', true);
    }

    btnRemoveFile.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFile = null;
        receiptFile.value = '';
        uploadPlaceholder.classList.remove('hidden');
        uploadPreview.classList.add('hidden');
        uploadZone.classList.remove('has-file');
        updateSubmitState();
        updateSidebar('receipt', false);
    });


    // ── 3. Name Field ──
    payUserName.addEventListener('input', () => {
        updateSubmitState();
    });


    // ── 4. Submit Payment ──
    btnSubmitPayment.addEventListener('click', async () => {
        if (!selectedFile || !payUserName.value.trim()) return;

        btnSubmitPayment.disabled = true;
        btnSubmitPayment.innerHTML = `
            <div class="mini-spinner"></div>
            Yuklanmoqda...
        `;

        try {
            const formData = new FormData();
            formData.append('receipt', selectedFile);
            formData.append('user_name', payUserName.value.trim());

            const resp = await fetch('/api/payment/submit', {
                method: 'POST',
                body: formData
            });

            const res = await resp.json();

            if (res.success) {
                currentPaymentId = res.payment_id;
                showStatusSection();
                document.getElementById('paymentIdDisplay').textContent = currentPaymentId;
                updateSidebar('submitted', true);

                // Start polling
                startPolling();

                // Update URL
                history.replaceState(null, '', `/payment?payment_id=${currentPaymentId}`);
            } else {
                alert(res.error || 'Xatolik yuz berdi');
                resetSubmitBtn();
            }
        } catch (e) {
            console.error('Submit error:', e);
            alert('Server bilan bog\'lanishda xatolik');
            resetSubmitBtn();
        }
    });

    function resetSubmitBtn() {
        btnSubmitPayment.disabled = false;
        btnSubmitPayment.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M22 2L11 13"/>
                <path d="M22 2L15 22L11 13L2 9L22 2Z"/>
            </svg>
            To'lovni yuborish
        `;
    }


    // ── 5. Status Section ──
    function showStatusSection() {
        document.getElementById('section-info').style.opacity = '0.5';
        document.getElementById('section-info').style.pointerEvents = 'none';
        document.getElementById('section-receipt').style.opacity = '0.5';
        document.getElementById('section-receipt').style.pointerEvents = 'none';
        document.getElementById('section-status').classList.remove('hidden');
        document.getElementById('section-status').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function startPolling() {
        pollTimer = setInterval(checkPaymentStatus, 5000);
    }

    async function checkPaymentStatus() {
        if (!currentPaymentId) return;
        try {
            const resp = await fetch(`/api/payment/status/${currentPaymentId}`);
            const res = await resp.json();

            if (res.success && res.payment) {
                const p = res.payment;

                if (p.status === 'approved') {
                    clearInterval(pollTimer);
                    showApproved();
                } else if (p.status === 'rejected') {
                    clearInterval(pollTimer);
                    showRejected(p.admin_note);
                } else if (p.status === 'reviewing') {
                    // Still waiting
                    showStatusSection();
                    document.getElementById('paymentIdDisplay').textContent = currentPaymentId;
                }
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }

    function showApproved() {
        document.getElementById('statusTitle').textContent = 'To\'lov tasdiqlandi!';
        document.getElementById('statusDesc').textContent = 'Biznes reja hujjatini yuklab olishingiz mumkin';
        document.getElementById('statusReviewing').classList.add('hidden');
        document.getElementById('statusApproved').classList.remove('hidden');
        document.getElementById('statusRejected').classList.add('hidden');
        updateSidebar('approved', true);
    }

    function showRejected(reason) {
        document.getElementById('statusTitle').textContent = 'To\'lov rad etildi';
        document.getElementById('statusDesc').textContent = 'Yangi chek yuklang';
        document.getElementById('statusReviewing').classList.add('hidden');
        document.getElementById('statusRejected').classList.remove('hidden');
        if (reason) {
            document.getElementById('rejectReason').textContent = reason;
        }
        updateSidebar('rejected', true);
    }


    // ── Helpers ──
    function updateSubmitState() {
        const ready = selectedFile && payUserName.value.trim().length > 0;
        btnSubmitPayment.disabled = !ready;
    }

    function updateSidebar(type, done) {
        if (type === 'receipt') {
            const el2 = document.getElementById('pay-check-3');
            const val3 = document.getElementById('receipt-status-val');
            if (done) {
                el2.classList.add('completed');
                val3.textContent = '✓';
                val3.style.color = 'var(--green-600)';
                updateProgress(50);
            } else {
                el2.classList.remove('completed');
                val3.textContent = '—';
                val3.style.color = '';
                updateProgress(25);
            }
        } else if (type === 'submitted') {
            const el = document.getElementById('pay-check-2');
            const val = document.getElementById('pay-status-val');
            el.classList.add('completed');
            val.textContent = '✓';
            val.style.color = 'var(--green-600)';
            updateProgress(75);
        } else if (type === 'approved') {
            const el = document.getElementById('pay-check-4');
            const val = document.getElementById('approval-status-val');
            el.classList.add('completed');
            val.textContent = 'Tasdiqlandi';
            val.style.color = 'var(--green-600)';
            updateProgress(100);
        } else if (type === 'rejected') {
            const el = document.getElementById('pay-check-4');
            const val = document.getElementById('approval-status-val');
            el.classList.remove('completed');
            val.textContent = 'Rad etildi';
            val.style.color = 'var(--red-500)';
        }
    }

    function updateProgress(pct) {
        document.getElementById('payProgressBar').style.width = pct + '%';
        document.getElementById('payProgressPercent').textContent = pct;
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    console.log('💳 Payment page loaded');
});
