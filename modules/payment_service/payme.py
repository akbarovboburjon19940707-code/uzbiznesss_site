"""
Payme Payment Provider — Placeholder
=======================================
Bu modul keyinchalik Payme to'lov tizimi integratsiyasi uchun tayyor.
Hozircha faqat struktura va interfeys yaratilgan.

Payme docs: https://developer.payme.uz/
"""
import logging
from typing import Dict, Any

from modules.payment_service import PaymentProvider, PaymentError

logger = logging.getLogger(__name__)


class PaymePaymentProvider(PaymentProvider):
    """
    Payme to'lov provayderi — hozircha placeholder.
    Keyinchalik to'liq integratsiya qo'shiladi.
    
    Payme integratsiya uchun kerak bo'ladi:
    - PAYME_MERCHANT_ID
    - PAYME_MERCHANT_KEY  
    - CheckPerformTransaction
    - CreateTransaction
    - PerformTransaction
    - CancelTransaction
    """

    @property
    def provider_name(self) -> str:
        return "payme"

    def create_payment_url(self, order_id: str, amount: float,
                           return_url: str = "") -> str:
        """
        Payme to'lov URL yaratish.
        TODO: Keyinchalik implement qilinadi.
        
        Payme URL format:
        https://checkout.paycom.uz/{base64_encoded_params}
        """
        raise PaymentError(
            "Payme to'lov tizimi hali ulanmagan. Tez orada qo'shiladi!",
            error_code=-100,
            details={"status": "not_implemented"}
        )

    def verify_callback(self, data: dict) -> Dict[str, Any]:
        """
        Payme callback tekshirish.
        TODO: Keyinchalik implement qilinadi.
        
        Payme JSONRPC format ishlatadi:
        - CheckPerformTransaction
        - CreateTransaction  
        - PerformTransaction
        - CancelTransaction
        """
        raise PaymentError(
            "Payme callback hali sozlanmagan",
            error_code=-100
        )

    def handle_callback(self, data: dict) -> Dict[str, Any]:
        """
        Payme callback handler.
        TODO: Keyinchalik implement qilinadi.
        
        Payme JSONRPC methods:
        - CheckPerformTransaction → buyurtma tekshirish
        - CreateTransaction → tranzaksiya yaratish
        - PerformTransaction → to'lovni amalga oshirish
        - CancelTransaction → bekor qilish
        """
        raise PaymentError(
            "Payme handler hali sozlanmagan",
            error_code=-100
        )


# ── Singleton instance ──
payme_provider = PaymePaymentProvider()
