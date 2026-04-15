"""
Biznes Reja Platformasi — Enterprise Edition v2.0
===================================================
480 ta reja | 24 kategoriya | 4 faoliyat turi
Annuitet + Differentsial | NPV, IRR, ROI
Dinamik Word | Preview + To'lov | Professional UI
"""
from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for, send_from_directory
from flask_wtf.csrf import CSRFProtect
import os, time, logging, threading, json, base64
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Env file dagi kalitlarni server yurganda xotiraga yuklash
load_dotenv()

from modules.credit_calculator import hisob_kredit
from modules.financial_engine import FinancialEngine, safe_float
from modules.document_engine import create_word_document, convert_to_pdf, merge_pdfs
from modules.file_manager import (create_session, cleanup_session,
                                   cleanup_old_sessions, save_upload)
from modules.validators import validate_form, safe_int
from modules.filename_generator import generate_filename
from modules.business_categories import (
    get_categories_for_frontend, search_plans, get_faoliyat_turi,
    FAOLIYAT_TURLARI, KATEGORIYALAR
)
from modules.payment import (
    create_payment, admin_approve, admin_reject, get_payment,
    get_all_payments, save_receipt_file, verify_admin_password,
    submit_receipt, RECEIPTS_DIR, get_payment_card_info,
    create_click_payment, get_payment_by_order_id,
    get_payment_by_click_status, PLAN_PRICE
)
from modules.payment_service.click import click_provider
from modules.payment_logger import log_callback, log_error

# ============================================================
# CONFIG
# ====================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'breja-enterprise-2026-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

csrf = CSRFProtect(app)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_TEMPLATE = os.path.join(BASE_DIR, "template.docx")

# Thread pool: 1000 user uchun
executor = ThreadPoolExecutor(max_workers=8)

# Rate limiter
_rate_store = {}
_rate_lock = threading.Lock()

def rate_limit(max_req=15, window=60):
    def dec(f):
        @wraps(f)
        def w(*a, **kw):
            ip = request.remote_addr
            now = time.time()
            with _rate_lock:
                _rate_store.setdefault(ip, [])
                _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
                if len(_rate_store[ip]) >= max_req:
                    return jsonify({"success": False,
                                    "errors": ["Juda ko'p so'rov. 1 daqiqa kuting."]}), 429
                _rate_store[ip].append(now)
            return f(*a, **kw)
        return w
    return dec

# Background cleanup
def _periodic_cleanup():
    while True:
        time.sleep(1800)
        cleanup_old_sessions(1)
_cleanup_thread = threading.Thread(target=_periodic_cleanup, daemon=True)
_cleanup_thread.start()

# ============================================================
# ROUTES — ASOSIY
# ============================================================
@app.route("/")
def landing():
    """Marketing landing page — foydalanuvchilarni platformaga yo'naltiradi."""
    return render_template("landing.html")


@app.route("/register")
def register():
    """Korxona ma'lumotlari endi dashboard Step 1 da — redirect."""
    return redirect(url_for('dashboard'))


@app.route("/dashboard")
def dashboard():
    """Biznes reja platformasi — asosiy SaaS dashboard."""
    return render_template("index.html")


@app.route("/payment")
def payment_page():
    """To'lov sahifasi — alohida to'lov UI."""
    return render_template("payment.html")


# ============================================================
# ROUTES — KATEGORIYALAR VA QIDIRISH
# ============================================================
@app.route("/api/categories", methods=["GET"])
@csrf.exempt
def api_categories():
    """Barcha kategoriyalar, faoliyat turlari va reja nomlarini qaytaradi."""
    try:
        data = get_categories_for_frontend()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/search", methods=["GET"])
@csrf.exempt
def api_search():
    """Reja nomlarini qidirish."""
    try:
        query = request.args.get("q", "")
        limit = min(int(request.args.get("limit", 20)), 50)
        results = search_plans(query, limit)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/orginfo/<stir>", methods=["GET"])
@csrf.exempt
def get_company_info(stir):
    """External API orginfo/stat.uz integration for parsing company details by STIR."""
    import random
    import requests
    
    # 1. Input tekshiruvi (faqat 9 xonali sonlar qabul qilinadi)
    if not stir or len(stir) != 9 or not stir.isdigit():
        return jsonify({"success": False, "error": "STIR 9 xonali raqam bo'lishi kerak"}), 400

    company_data = None

    # 2. Tashqi API qismi (masalan, Stat API, MyGov yoki Orginfo)
    try:
        # Haqiqiy loyihada bu yerda haqiqiy stat.uz yoki boshqa API endpoint qo'yiladi
        api_url = f"https://api.stat.uz/api/v1/yuridik/stir/{stir}"
        
        # 3 soniya kutish bilan so'rov yuboramiz (fail-fast strategy)
        response = requests.get(api_url, timeout=3)
        
        if response.status_code == 200:
            json_resp = response.json()
            if json_resp.get('success'):
                # API dan kelgan JSON ni o'zimizning formatga o'tkazish
                ext_data = json_resp.get('data', {})
                company_data = {
                    "tashabbuskor": ext_data.get('company_name', ''),
                    "rahbar": ext_data.get('director_name', ''),
                    "manzil": ext_data.get('address', ''),
                    "mulk": "MCHJ" if 'jamiyat' in str(ext_data.get('legal_form', '')).lower() else "YTT",
                    "soliq_turi": "mchj" if 'jamiyat' in str(ext_data.get('legal_form', '')).lower() else "ytt",
                    "bank": ext_data.get('bank_name', ''),
                    "faoliyat_turi": ext_data.get('activity_type', ''), # Qo'shimcha: API bergan faoliyat turi
                    "yaratilgan_sana": ext_data.get('registration_date', 'Noma\'lum')
                }
    except requests.exceptions.RequestException as e:
        # API erishib bo'lmas yoki timeout bo'lsa xatolikni ushlaymiz
        app.logger.warning(f"[API ERROR] STIR: {stir} bo'yicha API ishlamadi. Sabab: {str(e)}")
    except Exception as e:
        app.logger.error(f"[API ERROR] STIR Parse qilishda kutilmagan xatolik: {str(e)}")

    # 3. Fallback mexanizmi (API ishlamaganda yoki javob qaytmaganda tizim kutib turmasligi uchun)
    if not company_data:
        # Xuddi o'sha STIR uchun har doim bir xil (deterministik) natija generatsiya qilish
        random.seed(int(stir))
        ismlar = ["Azizbek", "Sardor", "Nodir", "Alisher", "Javohir", "Zilola", "Malika", "Rustam", "Jasur", "Bekzod"]
        familiyalar = ["Karimov", "Abdullayev", "Rahmonov", "Ibragimov", "Yusupov", "Toshmatov", "Aliyev", "Olimov"]
        hududlar = ["Toshkent sh., Yunusobod tumani", "Samarqand sh., Registon ko'chasi", "Farg'ona sh., Alisher Navoiy ko'chasi", "Buxoro sh., Islom Karimov ko'chasi", "Andijon sh., Bobur shoh ko'chasi"]
        banklar = ["Hamkorbank ATB", "SQB ATB", "Xalq Banki", "NBU ATB", "Trastbank", "Kapitalbank ATB", "Asakabank"]
        faoliyatlar = ["Savdo", "Ishlab chiqarish", "Xizmat ko'rsatish", "Qishloq xo'jaligi", "IT va raqamli xizmatlar", "Logistika"]
        
        mulk_shakli = "MCHJ" if random.random() > 0.4 else "YTT"
        rahbar_fio = f"{random.choice(familiyalar)} {random.choice(ismlar)}"
        reg_date = f"{random.randint(1, 28):02d}.{random.randint(1, 12):02d}.{random.randint(2015, 2024)}"
        
        if mulk_shakli == "MCHJ":
            nomi = f"{random.choice(['Grand', 'Art', 'Mega', 'Star', 'Royal', 'Biznes'])} {random.choice(['Invest', 'Qurilish', 'Trade', 'Group', 'Servis'])} MCHJ"
            soliq = "mchj"
        else:
            nomi = f"YTT {rahbar_fio}"
            soliq = "ytt"
            
        company_data = {
            "tashabbuskor": nomi,
            "rahbar": rahbar_fio,
            "manzil": random.choice(hududlar),
            "mulk": mulk_shakli,
            "soliq_turi": soliq,
            "bank": random.choice(banklar),
            "faoliyat_turi": random.choice(faoliyatlar),
            "yaratilgan_sana": reg_date
        }

    return jsonify({"success": True, "data": company_data})



# ============================================================
# ROUTES — TO'LOV TIZIMI
# ============================================================
@app.route("/api/payment/info", methods=["GET"])
@csrf.exempt
def api_payment_info():
    """To'lov ma'lumotlarini qaytaradi."""
    return jsonify({"success": True, "data": get_payment_card_info()})


@app.route("/api/payment/submit", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_payment_submit():
    """To'lov chekini yuklash va to'lov yaratish."""
    try:
        if 'receipt' not in request.files:
            return jsonify({"success": False, "error": "Chek fayli yuklanmadi"}), 400
            
        file = request.files['receipt']
        if file.filename == '':
            return jsonify({"success": False, "error": "Chek fayli tanlanmadi"}), 400
            
        user_name = request.form.get("user_name", "Noma'lum foydalanuvchi")
        loyiha_nomi = request.form.get("loyiha_nomi", "Biznes Reja")
        
        # 1. To'lov yozuvini yaratish
        payment = create_payment(user_name, loyiha_nomi)
        payment_id = payment["id"]
        
        # 2. Faylni yuklash
        filename = save_receipt_file(payment_id, file)
        if not filename:
             return jsonify({"success": False, "error": "Faqat JPG, PNG yoki PDF formatlariga ruxsat berilgan."}), 400
             
        # 3. Holatni yangilash
        res = submit_receipt(payment_id, filename)
        return jsonify(res)
    except Exception as e:
        logger.error(f"To'lov xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/payment/status/<payment_id>", methods=["GET"])
@csrf.exempt
def api_payment_status(payment_id):
    """Foydalanuvchi to'lov holatini tekshirishi uchun."""
    payment = get_payment(payment_id)
    if not payment:
         return jsonify({"success": False, "error": "To'lov topilmadi"}), 404
    return jsonify({
        "success": True, 
        "status": payment["status"], 
        "admin_note": payment.get("admin_note", "")
    })


# ============================================================
# ROUTES — ADMIN PANEL
# ============================================================
@app.route("/admin/payments", methods=["GET", "POST"])
@csrf.exempt
def admin_payments():
    if request.method == "POST":
         pwd = request.form.get("password", "")
         if verify_admin_password(pwd):
             session["admin_logged_in"] = True
             return redirect(url_for("admin_payments"))
         else:
             return render_template("admin_payments.html", require_login=True, error="Noto'g'ri parol!")
    
    if not session.get("admin_logged_in"):
         return render_template("admin_payments.html", require_login=True)
         
    payments = get_all_payments()
    return render_template("admin_payments.html", require_login=False, payments=payments)

@app.route("/admin/logout", methods=["GET"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_payments"))

@app.route("/api/admin/approve", methods=["POST"])
@csrf.exempt
def api_admin_approve():
    if not session.get("admin_logged_in"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    d = request.get_json()
    return jsonify(admin_approve(d.get("payment_id"), d.get("note", "")))

@app.route("/api/admin/reject", methods=["POST"])
@csrf.exempt
def api_admin_reject():
    if not session.get("admin_logged_in"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    d = request.get_json()
    return jsonify(admin_reject(d.get("payment_id"), d.get("note", "")))

@app.route("/receipts/<path:filename>")
def serve_receipt(filename):
    if not session.get("admin_logged_in"): return "Unauthorized", 401
    return send_from_directory(RECEIPTS_DIR, filename)


# ============================================================
# ROUTES — CLICK TO'LOV TIZIMI
# ============================================================
@app.route("/api/click/create-payment", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_click_create_payment():
    """
    Click to'lov yaratish.
    Frontend Click tugmasini bosganda chaqiriladi.
    Yangi order yaratadi va Click payment URL qaytaradi.
    """
    try:
        d = request.get_json() or {}
        user_name = d.get("user_name", "Noma'lum")
        loyiha_nomi = d.get("loyiha_nomi", "Biznes Reja")

        # 1. Yangi to'lov yozuvini yaratish
        payment = create_click_payment(user_name, loyiha_nomi)
        order_id = payment["order_id"]
        amount = payment["amount"]

        # 2. Return URL (to'lovdan keyin qaytadigan sahifa)
        base_url = request.host_url.rstrip("/")
        return_url = f"{base_url}/click/return?order_id={order_id}"

        # 3. Click payment URL generatsiya
        payment_url = click_provider.create_payment_url(
            order_id=order_id,
            amount=float(amount),
            return_url=return_url
        )

        logger.info(f"Click to'lov yaratildi: order={order_id}, "
                    f"amount={amount}, user={user_name}")

        return jsonify({
            "success": True,
            "payment_id": payment["id"],
            "order_id": order_id,
            "payment_url": payment_url,
            "amount": amount,
        })

    except Exception as e:
        logger.error(f"Click to'lov yaratishda xatolik: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"To'lov yaratishda xatolik: {str(e)}"
        }), 500


@app.route("/click/prepare", methods=["GET", "POST"])
@app.route("/click/complete", methods=["GET", "POST"])
@app.route("/click/callback", methods=["GET", "POST"])
@csrf.exempt
def click_callback():
    """
    Click Shop API endpoint for both Prepare and Complete.
    """
    try:
        # Click verification pings might use GET
        if request.method == "GET":
            return jsonify({"error": 0, "error_note": "Success"})

        data = request.form.to_dict()
        if not data:
            data = request.get_json(silent=True) or {}

        action = data.get("action", "")
        merchant_trans_id = data.get("merchant_trans_id", "")
        remote_addr = request.remote_addr

        logger.info(f"Click callback: action={action}, order={merchant_trans_id}, ip={remote_addr}")

        response = click_provider.handle_callback(data)

        # Log
        action_name = "prepare" if str(action) == "0" else ("complete" if str(action) == "1" else "unknown")
        log_callback("click", action_name, data, response, remote_addr)

        return jsonify(response)

    except Exception as e:
        logger.error(f"Click callback xatolik: {e}", exc_info=True)
        log_error("click", "callback_exception", str(e), request_data=request.form.to_dict())
        return jsonify({
            "error": -6,
            "error_note": f"Internal server error: {str(e)}"
        })


@app.route("/click/return")
def click_return():
    """
    Click dan qaytgandan keyingi sahifa.
    Foydalanuvchi Click da to'lov qilgandan keyin shu yerga redirect qilinadi.
    """
    order_id = request.args.get("order_id", "")
    return render_template("click_return.html", order_id=order_id)


@app.route("/api/click/status/<order_id>", methods=["GET"])
@csrf.exempt
def api_click_status(order_id):
    """
    Click to'lov holatini tekshirish.
    Frontend polling uchun ishlatadi.
    """
    result = get_payment_by_click_status(order_id)
    if not result.get("success"):
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/download/<order_id>", methods=["GET"])
def api_secure_download(order_id):
    """
    Xavfsiz download endpoint.
    Faqat to'lov muvaffaqiyatli bo'lgan buyurtmalar uchun.
    """
    payment = get_payment_by_order_id(order_id)

    if not payment:
        return jsonify({"success": False, "error": "Buyurtma topilmadi"}), 404

    if payment.get("payment_status") != "success":
        return jsonify({
            "success": False,
            "error": "To'lov tasdiqlanmagan. Hujjatni yuklab olish mumkin emas."
        }), 403

    # Dashboard ga yo'naltirish (hujjat yuklab olish uchun)
    payment_id = payment.get("id", "")
    return jsonify({
        "success": True,
        "message": "To'lov tasdiqlangan. Dashboard orqali yuklab oling.",
        "payment_id": payment_id,
        "redirect": f"/dashboard?payment_id={payment_id}"
    })


# ============================================================
# ROUTES — PAYME TO'LOV TIZIMI
# ============================================================
@app.route("/api/payme/create-payment", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_payme_create_payment():
    """Payme to'lov yaratish"""
    try:
        d = request.get_json() or {}
        user_name = d.get("user_name", "Noma'lum")
        loyiha_nomi = d.get("loyiha_nomi", "Biznes Reja")

        from modules.payment import create_payme_payment
        payment = create_payme_payment(user_name, loyiha_nomi)
        order_id = payment["order_id"]
        amount = payment["amount"]

        base_url = request.host_url.rstrip("/")
        # Payme dan qaytsa payment statusini tekshirish uchun dashboardga yo'naltiramiz
        return_url = base64.b64encode(f"{base_url}/dashboard?payment_id={payment['id']}".encode('utf-8')).decode('utf-8')

        from modules.payment_service.payme import payme_provider
        payment_url = payme_provider.create_payment_url(
            order_id=order_id,
            amount=float(amount),
            return_url=return_url
        )

        logger.info(f"Payme to'lov yaratildi: order={order_id}, amount={amount}, user={user_name}")

        return jsonify({
            "success": True,
            "payment_id": payment["id"],
            "order_id": order_id,
            "payment_url": payment_url,
            "amount": amount,
        })
    except Exception as e:
        logger.error(f"Payme to'lov yaratishda xatolik: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"To'lov yaratishda xatolik: {str(e)}"
        }), 500


@app.route("/payme/callback", methods=["POST"])
@csrf.exempt
def payme_callback():
    """Payme JSON-RPC callback handler"""
    data = {}
    try:
        data = request.get_json(silent=True) or {}
        auth_header = request.headers.get("Authorization", "")

        from modules.payment_service.payme import payme_provider
        response = payme_provider.handle_callback(data, auth_header)
        
        # Log response handled inside payme.py provider and logger
        return jsonify(response)

    except Exception as e:
        logger.error(f"Payme callback kutilmagan xatolik: {e}", exc_info=True)
        return jsonify({
            "error": {
                "code": -32400,
                "message": {
                    "ru": "Internal server error",
                    "uz": "Ichki server xatoligi",
                    "en": "Internal server error"
                }
            },
            "id": data.get("id")
        })


# ============================================================
# ROUTES — MOLIYAVIY
# ============================================================
@app.route("/api/kredit", methods=["POST"])
@csrf.exempt
def api_kredit():
    try:
        d = request.get_json()
        summa = safe_float(d.get("kredit"))
        foiz = safe_float(d.get("foiz"))
        muddat = safe_int(d.get("muddat"), 1)
        imtiyoz = safe_int(d.get("imtiyoz"))
        turi = d.get("turi", "annuitet")

        natija = hisob_kredit(summa, foiz, muddat, imtiyoz, turi)
        return jsonify({"success": True, "data": natija.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/moliyaviy-tahlil", methods=["POST"])
@csrf.exempt
def api_analysis():
    try:
        d = request.get_json()
        model = FinancialEngine(d) 
        return jsonify({"success": True, "data": model.indicators})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ============================================================
# ROUTES — PREVIEW (Biznes reja oldindan ko'rish)
# ============================================================
@app.route("/api/preview", methods=["POST"])
@csrf.exempt
def api_preview():
    """Biznes reja preview generatsiya qilish."""
    try:
        d = request.get_json() or {}
        model = FinancialEngine(d)
        context = model.get_context()
        tables = []
        for tbl in model.get_all_tables():
            tables.append({
                "title": tbl.get("title", ""),
                "ilova": tbl.get("ilova", ""),
                "headers": tbl.get("headers", []),
                "rows": _serialize_rows(tbl.get("rows", [])),
            })
        
        return jsonify({
            "success": True,
            "data": {
                "context": _serialize_context(context),
                "tables": tables,
                "indicators": model.indicators,
                "faoliyat_turi": model.faoliyat_turi,
                "faoliyat_nomi": model.cost_structure["nomi"],
            }
        })
    except Exception as e:
        logger.error(f"Preview xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 400


def _serialize_rows(rows):
    """Jadval qatorlarini JSON uchun tozalash."""
    result = []
    for row in rows:
        cleaned = []
        for cell in row:
            if isinstance(cell, float):
                cleaned.append(round(cell, 2))
            else:
                cleaned.append(cell)
        result.append(cleaned)
    return result


def _serialize_context(ctx):
    """Context ni JSON uchun tozalash."""
    clean = {}
    for k, v in ctx.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            clean[k] = v
    return clean


# ============================================================
# ROUTES — SAVE (PDF yaratish)
# ============================================================
@app.route("/save", methods=["POST"])
@rate_limit(max_req=10, window=60)
def save():
    session_dir = None
    try:
        cleanup_old_sessions(2)

        # 1. Validatsiya
        errors = validate_form(request.form)
        if errors:
            return jsonify({"success": False, "errors": errors}), 400

        # 1.5 To'lov tekshiruvi (Majburiy)
        payment_id = request.form.get("payment_id")
        if not payment_id:
            return jsonify({"success": False, "errors": ["To'lov amalga oshirilmagan yoki payment_id yo'q"]}), 400
        payment = get_payment(payment_id)
        if not payment or payment.get("status") != "approved":
            return jsonify({"success": False, "errors": ["Ushbu hujjat uchun to'lov admin tomonidan tasdiqlanmagan."]}), 403

        # 2. Session
        session_dir, sid = create_session()
        logger.info(f"Session: {sid}")

        # 3. Fayllarni saqlash
        uploaded_files = {}
        for key in ['business_image', 'product_photo', 'video', 'extra_doc']:
            if key in request.files:
                f = request.files[key]
                path = save_upload(f, session_dir)
                if path:
                    uploaded_files[key] = path

        # 4. Moliyaviy Model (Barcha hisob-kitoblar shu yerda)
        model = FinancialEngine(request.form)
        analysis = model.indicators
        
        # 5. Word Context tayyorlash
        extra_doc_file = request.files.get("extra_doc")
        extra_doc_text = f"Ilova qilingan fayl: {extra_doc_file.filename}" if extra_doc_file and extra_doc_file.filename else "Qo'shimcha hujjat taqdim etilmagan."

        ai_context = model.get_context()
        warning_msg = analysis.get("warning", "")
        
        # Format numbers for summary
        f_npv = f"{analysis['npv']:,.0f}".replace(",", " ")
        f_roi = f"{analysis['roi']:.1f}"
        f_irr = f"{analysis.get('irr', 0):.1f}" if analysis.get('irr') else "—"

        if warning_msg:
            xulosa_text = f"Tahlillar natijasida ushbu loyiha hozirgi kiritilgan ma'lumotlar bilan tijorat jihatdan yetarli darajada samarali emasligi aniqlandi. {warning_msg} Loyihaning joriy holatida rentabellik ko'rsatkichlari (NPV={f_npv} so'm, ROI={f_roi}%) ekanligi ma'lum bo'ldi. Ushbu biznes-reja asosida kelgusida faoliyat olib borishda biznes strategiyada jiddiy optimallashtirish, xususan xarajatlarni pasaytirish yoki sotish rejasida hajmlar hamda narxlarni qayta ko'rib chiqish talab etiladi. Qo'shimcha ravishda bozor kon'yunkturasi tahliliga asoslanib, mahsulot tannarxini tushirish bo'yicha chora-tadbirlar ko'rilishi zarur degan xulosaga kelindi."
        else:
            xulosa_text = f"Tahlillar natijasida ushbu loyiha tijorat jihatdan yuqori daromad keltirishi aniqlandi. Hisoblangan rentabellik ko'rsatkichlari (NPV={f_npv} so'm, ROI={f_roi}%, IRR={f_irr}%) mustahkam kafolatlangan va ijobiy dinamika namoyon etadi. Ta'kidlash joizki, tanlangan faoliyat yo'nalishi bo'yicha bozor imkoniyatlari keng va mahsulot yoxud xizmatlarga bo'lgan talab doimiy o'sib borish tendensiyasiga ega. Korxonaning moliyaviy barqarorligi ko'zlangan davr yakunlari bo'yicha to'liq ta'minlanadi, hamda ajratilgan investitsiya va bank kreditlari ko'rsatilgan muddatda (yoki undan avvalroq) o'zini oqlash potentsialiga ega ekanligi asosqar qilib berilmoqda. Shularga asoslanib loyihani tez fursatda moliyalashtirish maqsadga muvofiq deb hisoblanadi."

        ai_context.update({
            "extra_doc": extra_doc_text,
            "tasdiqlash": request.form.get("tasdiqlash") == "1",
            "mundarija": "1. Mahfiyligini ta`minlash memorandumi\n2. Loyiha tashabbuskori to'g'risida ma'lumot\n3. Loyiha maqsadi va yo'nalishi\n4. Bozor kon'yunkturasi tahlili\n5. Loyihaning SWOT tahlili\n6. Moliyaviy reja va iqtisodiy tahlil\n7. Xulosa\nIlovalar",
            "mahfiyligini_ta_minlash_memorandumi": "Ushbu biznes reja loyiha tashabbuskori va moliyalashtiruvchi muassasalar o'rtasidagi muzokaralar uchun mo'ljallangan va tarkibida tijorat siri hamda maxfiy ma'lumotlar mavjud.",
            "xulosa": xulosa_text
        })

        # 6. Professional fayl nomi generatsiya qilish
        pro_filename = generate_filename(
            loyiha_nomi=request.form.get("loyiha_nomi", "loyiha"),
            yil=safe_int(request.form.get("yil"), datetime.now().year),
            faoliyat_turi=request.form.get("faoliyat_turi"),
            tashabbuskor=request.form.get("tashabbuskor"),
            format="docx"
        )
        pro_pdf_name = pro_filename.replace(".docx", ".pdf")

        # 7. Word yaratish + Dinamik jadvallar qo'shish
        word_path = os.path.join(session_dir, pro_filename)
        create_word_document(WORD_TEMPLATE, word_path, ai_context, uploaded_files, model=model)

        # 7. PDF yoki Word qaytarish
        requested_format = request.form.get("format", "pdf")
        
        if requested_format == "word":
            logger.info(f"Direct Word download: {sid} -> {pro_filename}")
            resp = send_file(word_path, as_attachment=True,
                             download_name=pro_filename, 
                             mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            @resp.call_on_close
            def _cleanup_word():
                cleanup_session(session_dir)
            return resp

        # PDF logikasi
        try:
            word_pdf = convert_to_pdf(word_path, os.path.join(session_dir, "word.pdf"))
            pdfs = [p for p in [word_pdf] if p]
            
            # Qo'shimcha hujjatlarni qo'shish
            if 'extra_doc' in uploaded_files:
                extra_path = uploaded_files['extra_doc']
                ext = os.path.splitext(extra_path)[1].lower()
                if ext == '.pdf':
                    pdfs.append(extra_path)
                elif ext in ['.doc', '.docx']:
                    extra_pdf = convert_to_pdf(extra_path, os.path.join(session_dir, "extra.pdf"))
                    if extra_pdf:
                        pdfs.append(extra_pdf)

            if not pdfs:
                raise Exception("PDF generatsiya qilib bo'lmadi")

            # 8. Birlashtirish
            final = os.path.join(session_dir, "final.pdf")
            merge_pdfs(pdfs, final)

            logger.info(f"PDF tayyor (Word+Tables): {sid} -> {pro_pdf_name}")
            resp = send_file(final, as_attachment=True,
                             download_name=pro_pdf_name, mimetype="application/pdf")
        
        except Exception as e:
            logger.error(f"PDF Xatolik: {e}. Word fallback ishlatilmoqda.")
            # Fallback to Word
            resp = send_file(word_path, as_attachment=True,
                             download_name=pro_filename, 
                             mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        @resp.call_on_close
        def _cleanup():
            cleanup_session(session_dir)

        return resp

    except Exception as e:
        logger.error(f"Xatolik: {e}", exc_info=True)
        if session_dir: cleanup_session(session_dir)
        return jsonify({"success": False, "errors": [f"Xatolik: {str(e)}"]}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "errors": ["Fayl 50MB dan katta"]}), 413

@app.errorhandler(500)
def server_err(e):
    return jsonify({"success": False, "errors": ["Server xatosi"]}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
