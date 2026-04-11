"""
To'lov Moduli — Bank kartasiga o'tkazma + Admin tasdiqlash
============================================================
Karta: 9860 0401 0203 1362 (Akbarov B)
Narx: 80,000 so'm
"""
import uuid
import time
import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Narx va karta ma'lumotlari
PLAN_PRICE = 80_000
CARD_NUMBER = "9860 0401 0203 1362"
CARD_HOLDER = "Akbarov B"

# Admin parol (production da env variable bo'lishi kerak)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

# To'lovlar saqlash fayli
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYMENTS_DIR = os.path.join(BASE_DIR, "payments_data")
PAYMENTS_FILE = os.path.join(PAYMENTS_DIR, "payments.json")
RECEIPTS_DIR = os.path.join(PAYMENTS_DIR, "receipts")

# Papkalarni yaratish
os.makedirs(PAYMENTS_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


def _load_payments() -> Dict[str, dict]:
    """JSON fayldan to'lovlarni yuklash."""
    if os.path.exists(PAYMENTS_FILE):
        try:
            with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_payments(payments: Dict[str, dict]):
    """To'lovlarni JSON faylga saqlash."""
    try:
        with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(payments, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"To'lovlarni saqlashda xatolik: {e}")


def create_payment(user_name: str, loyiha_nomi: str = "") -> dict:
    """Yangi to'lov yaratish."""
    payments = _load_payments()
    payment_id = str(uuid.uuid4())[:12]

    payment = {
        "id": payment_id,
        "user_name": user_name,
        "loyiha_nomi": loyiha_nomi,
        "amount": PLAN_PRICE,
        "status": "pending",  # pending | reviewing | approved | rejected
        "receipt_file": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submitted_at": None,
        "reviewed_at": None,
        "admin_note": "",
    }

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"To'lov yaratildi: {payment_id}, user: {user_name}")
    return payment


def submit_receipt(payment_id: str, receipt_filename: str) -> dict:
    """Chek yuklandi — tekshirishga yuborish."""
    payments = _load_payments()
    payment = payments.get(payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment["receipt_file"] = receipt_filename
    payment["status"] = "reviewing"
    payment["submitted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"Chek yuklandi: {payment_id}, fayl: {receipt_filename}")
    return {"success": True, "payment": payment}


def admin_approve(payment_id: str, admin_note: str = "") -> dict:
    """Admin to'lovni tasdiqlash."""
    payments = _load_payments()
    payment = payments.get(payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment["status"] = "approved"
    payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payment["admin_note"] = admin_note

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"To'lov tasdiqlandi: {payment_id}")
    return {"success": True, "payment": payment}


def admin_reject(payment_id: str, reason: str = "") -> dict:
    """Admin to'lovni rad etish."""
    payments = _load_payments()
    payment = payments.get(payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment["status"] = "rejected"
    payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payment["admin_note"] = reason
    payment["receipt_file"] = None  # Qayta yuklash uchun

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"To'lov rad etildi: {payment_id}, sabab: {reason}")
    return {"success": True, "payment": payment}


def get_payment(payment_id: str) -> Optional[dict]:
    """Bitta to'lovni olish."""
    payments = _load_payments()
    return payments.get(payment_id)


def get_all_payments() -> List[dict]:
    """Barcha to'lovlarni olish (admin uchun)."""
    payments = _load_payments()
    result = list(payments.values())
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


def save_receipt_file(payment_id: str, file_storage) -> Optional[str]:
    """Chek faylini saqlash."""
    if not file_storage or not file_storage.filename:
        return None

    ext = os.path.splitext(file_storage.filename)[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}
    if ext not in allowed:
        return None

    filename = f"{payment_id}_{int(time.time())}{ext}"
    filepath = os.path.join(RECEIPTS_DIR, filename)
    file_storage.save(filepath)
    logger.info(f"Chek saqlandi: {filepath}")
    return filename


def get_payment_card_info() -> dict:
    """Frontend uchun karta ma'lumotlari."""
    return {
        "card_number": CARD_NUMBER,
        "card_holder": CARD_HOLDER,
        "price": PLAN_PRICE,
        "price_formatted": f"{PLAN_PRICE:,}".replace(",", " ") + " so'm",
    }


def verify_admin_password(password: str) -> bool:
    """Admin parolni tekshirish."""
    return password == ADMIN_PASSWORD
