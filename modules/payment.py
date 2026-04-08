"""
To'lov Moduli — Demo rejim
============================
Click va Payme to'lov integratsiyasi (demo).
Narx: 80,000 so'm
"""
import uuid
import time
import hashlib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Narx (so'mda)
PLAN_PRICE = 80_000
PLAN_PRICE_TIYIN = PLAN_PRICE * 100  # Payme tiyinda ishlaydi

# Demo merchant ma'lumotlari
CLICK_MERCHANT_ID = "DEMO_CLICK_MERCHANT"
CLICK_SERVICE_ID = "DEMO_CLICK_SERVICE"
CLICK_SECRET_KEY = "DEMO_CLICK_SECRET"

PAYME_MERCHANT_ID = "DEMO_PAYME_MERCHANT"
PAYME_SECRET_KEY = "DEMO_PAYME_SECRET"

# In-memory to'lov holatlari (production da database bo'ladi)
_payments: Dict[str, dict] = {}


def create_payment(method: str = "demo") -> dict:
    """Yangi to'lov yaratish."""
    payment_id = str(uuid.uuid4())[:12]
    payment = {
        "id": payment_id,
        "method": method,
        "amount": PLAN_PRICE,
        "amount_tiyin": PLAN_PRICE_TIYIN,
        "status": "pending",
        "created_at": time.time(),
        "paid_at": None,
    }
    _payments[payment_id] = payment
    logger.info(f"To'lov yaratildi: {payment_id}, usul: {method}, summa: {PLAN_PRICE}")
    return payment


def verify_payment(payment_id: str) -> dict:
    """To'lovni tekshirish (demo rejimda har doim muvaffaqiyatli)."""
    payment = _payments.get(payment_id)
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}
    
    # Demo rejimda avtomatik tasdiqlash
    payment["status"] = "paid"
    payment["paid_at"] = time.time()
    _payments[payment_id] = payment
    logger.info(f"To'lov tasdiqlandi (demo): {payment_id}")
    
    return {"success": True, "payment": payment}


def get_payment(payment_id: str) -> Optional[dict]:
    """To'lov holatini olish."""
    return _payments.get(payment_id)


def get_click_url(payment_id: str) -> str:
    """Click to'lov URL yaratish (demo)."""
    return (
        f"https://my.click.uz/services/pay?"
        f"service_id={CLICK_SERVICE_ID}"
        f"&merchant_id={CLICK_MERCHANT_ID}"
        f"&amount={PLAN_PRICE}"
        f"&transaction_param={payment_id}"
        f"&return_url=http://localhost:5000/payment/success/{payment_id}"
    )


def get_payme_url(payment_id: str) -> str:
    """Payme to'lov URL yaratish (demo)."""
    import base64
    params = f"m={PAYME_MERCHANT_ID};ac.order_id={payment_id};a={PLAN_PRICE_TIYIN}"
    encoded = base64.b64encode(params.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"


def get_payment_info() -> dict:
    """Frontend uchun to'lov ma'lumotlari."""
    return {
        "price": PLAN_PRICE,
        "price_formatted": f"{PLAN_PRICE:,}".replace(",", " ") + " so'm",
        "methods": [
            {
                "id": "click",
                "name": "Click",
                "icon": "💳",
                "color": "#00b4ff",
                "description": "Click orqali to'lash",
            },
            {
                "id": "payme",
                "name": "Payme",
                "icon": "📱",
                "color": "#00cccc",
                "description": "Payme orqali to'lash",
            },
            {
                "id": "card",
                "name": "Karta orqali",
                "icon": "💳",
                "color": "#6366f1",
                "description": "Bevosita karta raqami orqali",
            },
            {
                "id": "demo",
                "name": "Demo (Test)",
                "icon": "🧪",
                "color": "#10b981",
                "description": "Test rejimda bepul yuklab olish",
            },
        ],
    }
