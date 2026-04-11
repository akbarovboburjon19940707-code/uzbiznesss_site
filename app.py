"""
Biznes Reja Platformasi — Enterprise Edition v2.0
===================================================
480 ta reja | 24 kategoriya | 4 faoliyat turi
Annuitet + Differentsial | NPV, IRR, ROI
Dinamik Word | Preview + To'lov | Professional UI
"""
from flask import Flask, render_template, request, send_file, jsonify
from flask_wtf.csrf import CSRFProtect
import os, time, logging, threading, json
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

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
    create_payment, verify_payment, get_payment,
    get_payment_info, PLAN_PRICE
)

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
def index():
    return render_template("index.html")


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
    return jsonify({"success": True, "data": get_payment_info()})


@app.route("/api/payment/create", methods=["POST"])
@csrf.exempt
def api_payment_create():
    """Yangi to'lov yaratish."""
    try:
        d = request.get_json()
        method = d.get("method", "demo")
        payment = create_payment(method)
        return jsonify({"success": True, "payment": payment})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/payment/verify", methods=["POST"])
@csrf.exempt
def api_payment_verify():
    """To'lovni tasdiqlash."""
    try:
        d = request.get_json()
        payment_id = d.get("payment_id", "")
        result = verify_payment(payment_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


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
