"""
To'lov Moduli — Bank kartasiga o'tkazma + Admin tasdiqlash + Click/Payme
==========================================================================
Karta: 9860 0401 0203 1362 (Akbarov B)
Narx: 80,000 so'm

Provayderlar: card (manual), click (auto), payme (coming soon)
"""
import uuid
import time
import os
import json
import logging
import threading
import hashlib
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Thread safety lock
_payments_lock = threading.Lock()

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

# Order counter fayli (Click uchun unikal raqamli order_id)
ORDER_COUNTER_FILE = os.path.join(PAYMENTS_DIR, "order_counter.json")

# Papkalarni yaratish
os.makedirs(PAYMENTS_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


def _load_payments() -> Dict[str, dict]:
    """JSON fayldan to'lovlarni yuklash (thread-safe)."""
    with _payments_lock:
        if os.path.exists(PAYMENTS_FILE):
            try:
                with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}


def _save_payments(payments: Dict[str, dict]):
    """To'lovlarni JSON faylga saqlash (thread-safe)."""
    with _payments_lock:
        try:
            with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(payments, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"To'lovlarni saqlashda xatolik: {e}")


def _generate_order_id() -> str:
    """
    Unikal raqamli order_id generatsiya qilish.
    Click uchun merchant_trans_id sifatida ishlatiladi.
    Format: timestamp_random  (masalan: 1713024000_7a3b)
    """
    ts = int(time.time())
    rand = uuid.uuid4().hex[:4]
    return f"{ts}_{rand}"


# ============================================================
# MAVJUD FUNKSIYALAR — KARTA ORQALI TO'LOV (O'ZGARMAGAN)
# ============================================================

def create_payment(user_name: str, loyiha_nomi: str = "") -> dict:
    """Yangi to'lov yaratish (karta orqali — mavjud tizim)."""
    payments = _load_payments()
    payment_id = str(uuid.uuid4())[:12]

    payment = {
        "id": payment_id,
        "order_id": _generate_order_id(),
        "user_name": user_name,
        "loyiha_nomi": loyiha_nomi,
        "amount": PLAN_PRICE,
        "payment_provider": "card",
        "payment_status": "pending",
        "status": "pending",  # pending | reviewing | approved | rejected
        "receipt_file": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submitted_at": None,
        "reviewed_at": None,
        "updated_at": None,
        "admin_note": "",
        "click_trans_id": None,
        "merchant_prepare_id": None,
    }

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"To'lov yaratildi: {payment_id}, user: {user_name}, provider: card")
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
    payment["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    payment["payment_status"] = "success"
    payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payment["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    payment["payment_status"] = "failed"
    payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payment["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payment["admin_note"] = reason

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


# ============================================================
# YANGI FUNKSIYALAR — CLICK / PAYME TO'LOV TIZIMI
# ============================================================

def create_click_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None) -> dict:
    """
    Click to'lov uchun yangi buyurtma yaratish.
    
    Args:
        user_name: Foydalanuvchi ismi
        loyiha_nomi: Loyiha/biznes reja nomi
        product_id: Mahsulot ID (ixtiyoriy)
    
    Returns:
        Yangi to'lov yozuvi (order_id bilan)
    """
    payments = _load_payments()
    payment_id = str(uuid.uuid4())[:12]
    order_id = _generate_order_id()

    payment = {
        "id": payment_id,
        "order_id": order_id,
        "user_name": user_name,
        "loyiha_nomi": loyiha_nomi,
        "product_id": product_id,
        "amount": PLAN_PRICE,
        "payment_provider": "click",
        "payment_status": "pending",   # pending | preparing | success | failed
        "status": "pending",           # umumiy status (mavjud tizim uchun)
        "receipt_file": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submitted_at": None,
        "reviewed_at": None,
        "updated_at": None,
        "admin_note": "",
        "click_trans_id": None,
        "merchant_prepare_id": None,
    }

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"Click to'lov yaratildi: {payment_id}, order: {order_id}, "
                f"user: {user_name}")
    return payment


def get_payment_by_order_id(order_id: str) -> Optional[dict]:
    """
    order_id bo'yicha to'lovni topish.
    Click callback larda merchant_trans_id = order_id.
    
    Args:
        order_id: Buyurtma raqami
    
    Returns:
        To'lov yozuvi yoki None
    """
    payments = _load_payments()
    for payment in payments.values():
        if payment.get("order_id") == order_id:
            return payment
    return None


def update_click_payment_status(order_id: str, status: str,
                                click_trans_id: str = None) -> Optional[dict]:
    """
    Click to'lov holatini yangilash.
    
    Args:
        order_id: Buyurtma raqami (merchant_trans_id)
        status: Yangi holat (preparing, success, failed)
        click_trans_id: Click tranzaksiya ID
    
    Returns:
        Yangilangan to'lov yozuvi yoki None
    """
    payments = _load_payments()
    
    # order_id bo'yicha payment topish
    target_id = None
    for pid, payment in payments.items():
        if payment.get("order_id") == order_id:
            target_id = pid
            break
    
    if not target_id:
        logger.error(f"Click status update: order topilmadi: {order_id}")
        return None
    
    payment = payments[target_id]
    payment["payment_status"] = status
    payment["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if click_trans_id:
        payment["click_trans_id"] = click_trans_id
    
    # Umumiy status ham yangilanadi
    if status == "success":
        payment["status"] = "approved"
        payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif status == "failed":
        payment["status"] = "rejected"
        payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif status == "preparing":
        payment["status"] = "reviewing"
        payment["merchant_prepare_id"] = target_id
    
    payments[target_id] = payment
    _save_payments(payments)
    logger.info(f"Click to'lov yangilandi: order={order_id}, status={status}, "
                f"click_trans={click_trans_id}")
    return payment


def is_payment_already_completed(order_id: str) -> bool:
    """
    To'lov allaqachon muvaffaqiyatli yakunlanganmi tekshirish.
    Replay attack oldini olish uchun.
    
    Args:
        order_id: Buyurtma raqami
    
    Returns:
        True agar to'lov allaqachon success bo'lsa
    """
    payment = get_payment_by_order_id(order_id)
    if not payment:
        return False
    return payment.get("payment_status") == "success"


def get_payment_by_click_status(order_id: str) -> dict:
    """
    Click to'lov holati haqida ma'lumot (frontend uchun).
    
    Args:
        order_id: Buyurtma raqami
    
    Returns:
        {success, status, payment_id, ...}
    """
    payment = get_payment_by_order_id(order_id)
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}
    
    return {
        "success": True,
        "payment_id": payment.get("id"),
        "order_id": payment.get("order_id"),
        "status": payment.get("payment_status", "pending"),
        "payment_provider": payment.get("payment_provider", "unknown"),
        "amount": payment.get("amount", 0),
        "created_at": payment.get("created_at"),
        "updated_at": payment.get("updated_at"),
    }

def create_payme_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None) -> dict:
    """Payme to'lov uchun yangi buyurtma yaratish."""
    payments = _load_payments()
    payment_id = str(uuid.uuid4())[:12]
    order_id = _generate_order_id()

    payment = {
        "id": payment_id,
        "order_id": order_id,
        "user_name": user_name,
        "loyiha_nomi": loyiha_nomi,
        "product_id": product_id,
        "amount": PLAN_PRICE,
        "payment_provider": "payme",
        "payment_status": "pending",
        "status": "pending",
        "receipt_file": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submitted_at": None,
        "reviewed_at": None,
        "updated_at": None,
        "admin_note": "",
        "payme_trans_id": None,
        "payme_create_time": None,
        "payme_perform_time": None,
        "payme_cancel_time": None,
        "payme_cancel_reason": None,
    }

    payments[payment_id] = payment
    _save_payments(payments)
    logger.info(f"Payme to'lov yaratildi: {payment_id}, order: {order_id}, user: {user_name}")
    return payment

def update_payme_payment_status(order_id: str, status: str, payme_trans_id: str = None, 
                                create_time: int = None, perform_time: int = None, 
                                cancel_time: int = None, reason: int = None) -> Optional[dict]:
    """Payme to'lov holatini yangilash."""
    payments = _load_payments()
    
    target_id = None
    for pid, payment in payments.items():
        if payment.get("order_id") == order_id:
            target_id = pid
            break
            
    if not target_id:
        logger.error(f"Payme status update: order topilmadi: {order_id}")
        return None
        
    payment = payments[target_id]
    payment["payment_status"] = status
    payment["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if payme_trans_id: payment["payme_trans_id"] = payme_trans_id
    if create_time: payment["payme_create_time"] = create_time
    if perform_time: payment["payme_perform_time"] = perform_time
    if cancel_time: payment["payme_cancel_time"] = cancel_time
    if reason is not None: payment["payme_cancel_reason"] = reason
    
    if status == "success":
        payment["status"] = "approved"
        payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif status == "failed":
        payment["status"] = "rejected"
        payment["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif status == "preparing":
        payment["status"] = "reviewing"
    
    payments[target_id] = payment
    _save_payments(payments)
    logger.info(f"Payme to'lov yangilandi: order={order_id}, status={status}, trans={payme_trans_id}")
    return payment

def get_payment_by_payme_trans_id(trans_id: str) -> Optional[dict]:
    """payme_trans_id bo'yicha to'lovni topish."""
    payments = _load_payments()
    for payment in payments.values():
        if payment.get("payme_trans_id") == trans_id:
            return payment
    return None
