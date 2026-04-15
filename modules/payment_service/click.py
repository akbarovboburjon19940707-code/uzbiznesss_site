"""
Click Shop API — Production Integration
==========================================
Click to'lov tizimi bilan to'liq integratsiya.
Prepare + Complete callback handlers.
MD5 signature verification.

Click docs: https://docs.click.uz/
"""
import os
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from modules.payment_service import PaymentProvider, PaymentError
from modules.payment_logger import log_callback, log_transaction, log_error

logger = logging.getLogger(__name__)

# ── Click credentials (env variables) ──
CLICK_MERCHANT_ID = os.environ.get("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.environ.get("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_USER_ID = os.environ.get("CLICK_MERCHANT_USER_ID", "")
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY", "")

# ── Click error codes ──
CLICK_ERROR_SUCCESS = 0
CLICK_ERROR_SIGN_CHECK_FAILED = -1
CLICK_ERROR_INCORRECT_AMOUNT = -2
CLICK_ERROR_ACTION_NOT_FOUND = -3
CLICK_ERROR_ALREADY_PAID = -4
CLICK_ERROR_ORDER_NOT_FOUND = -5
CLICK_ERROR_TRANSACTION_ERROR = -6
CLICK_ERROR_UPDATE_FAILED = -7
CLICK_ERROR_ORDER_CANCELLED = -9

# Click payment URL
CLICK_PAYMENT_URL = "https://my.click.uz/services/pay"


class ClickPaymentProvider(PaymentProvider):
    """
    Click Shop API to'lov provayderi.
    Prepare va Complete callback lar bilan ishlaydi.
    """

    @property
    def provider_name(self) -> str:
        return "click"

    def create_payment_url(self, order_id: str, amount: float,
                           return_url: str = "") -> str:
        """
        Click to'lov URL yaratish.
        Foydalanuvchini my.click.uz ga yo'naltirish uchun URL generatsiya qiladi.

        Args:
            order_id: Ichki buyurtma raqami (merchant_trans_id sifatida)
            amount: To'lov summasi (so'm)
            return_url: To'lovdan keyin qaytariladigan URL

        Returns:
            Click to'lov sahifasi URL
        """
        import urllib.parse
        
        if not all([CLICK_MERCHANT_ID, CLICK_SERVICE_ID]):
            raise PaymentError(
                "Click credentials sozlanmagan",
                error_code=-100,
                details={"missing": "CLICK_MERCHANT_ID or CLICK_SERVICE_ID"}
            )

        params = {
            "service_id": CLICK_SERVICE_ID,
            "merchant_id": CLICK_MERCHANT_ID,
            "amount": f"{amount:.2f}",
            "transaction_param": order_id,
            "return_url": return_url,
        }

        if CLICK_MERCHANT_USER_ID:
            params["merchant_user_id"] = CLICK_MERCHANT_USER_ID

        # URL query string yasash
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{CLICK_PAYMENT_URL}?{query}"

        log_transaction("click", order_id, "url_created", amount,
                        details={"payment_url": url})
        return url

    def verify_signature(self, data: dict, action: int) -> bool:
        """
        Click sign_string ni MD5 orqali tekshirish.

        Prepare (action=0):
          MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
              + amount + action + sign_time)

        Complete (action=1):
          MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
              + merchant_prepare_id + amount + action + sign_time)

        Args:
            data: Click dan kelgan form data
            action: 0 = Prepare, 1 = Complete

        Returns:
            True agar signature to'g'ri bo'lsa
        """
        received_sign = data.get("sign_string", "")
        click_trans_id = str(data.get("click_trans_id", ""))
        service_id = str(data.get("service_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = str(data.get("amount", ""))
        sign_time = str(data.get("sign_time", ""))

        if action == 0:
            # Prepare signature
            sign_str = (click_trans_id + service_id + CLICK_SECRET_KEY +
                        merchant_trans_id + amount + str(action) + sign_time)
        elif action == 1:
            # Complete signature
            merchant_prepare_id = str(data.get("merchant_prepare_id", ""))
            sign_str = (click_trans_id + service_id + CLICK_SECRET_KEY +
                        merchant_trans_id + merchant_prepare_id +
                        amount + str(action) + sign_time)
        else:
            return False

        computed_sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

        # Debug logging (safe version)
        masked_secret = "*" * len(CLICK_SECRET_KEY)
        debug_str = sign_str.replace(CLICK_SECRET_KEY, masked_secret)
        logger.info(f"[CLICK SIGN DEBUG] Order: {merchant_trans_id}, Action: {action}, "
                    f"SignStr: {debug_str}, Computed: {computed_sign}, Received: {received_sign}")

        if computed_sign != received_sign:
            log_error("click", "signature_invalid",
                      f"Expected: {computed_sign}, Got: {received_sign}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return False

        return True

    def verify_callback(self, data: dict) -> Dict[str, Any]:
        """Click callback ma'lumotlarini tekshirish."""
        action = int(data.get("action", -1))
        if not self.verify_signature(data, action):
            return {"success": False, "error": "Signature verification failed"}
        return {"success": True, "action": action}

    def handle_callback(self, data: dict) -> Dict[str, Any]:
        """
        Click callback so'rovini qayta ishlash.
        action=0 → Prepare, action=1 → Complete

        Args:
            data: Click dan kelgan POST form data

        Returns:
            Click formatida JSON javob
        """
        action = int(data.get("action", -1))

        if action == 0:
            return self._handle_prepare(data)
        elif action == 1:
            return self._handle_complete(data)
        else:
            log_error("click", "unknown_action",
                      f"Unknown action: {action}",
                      request_data=data)
            return self._error_response(
                data, CLICK_ERROR_ACTION_NOT_FOUND,
                "Action not found"
            )

    def _handle_prepare(self, data: dict) -> Dict[str, Any]:
        """
        Prepare callback — buyurtmani tekshirish va tasdiqlash.
        Click bu so'rovni to'lov boshlanishida yuboradi.

        Tekshiruvlar:
        1. Signature tekshirish
        2. Buyurtma mavjudligini tekshirish
        3. Buyurtma allaqachon to'langanligini tekshirish
        4. Summani tekshirish
        """
        # Lazy import to avoid circular dependency
        from modules.payment import (
            get_payment_by_order_id, is_payment_already_completed,
            update_click_payment_status
        )

        click_trans_id = str(data.get("click_trans_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = data.get("amount", "0")

        # 1. Signature tekshirish
        if not self.verify_signature(data, 0):
            return self._error_response(
                data, CLICK_ERROR_SIGN_CHECK_FAILED,
                "SIGN CHECK FAILED!"
            )

        # 2. Buyurtma mavjudligini tekshirish
        payment = get_payment_by_order_id(merchant_trans_id)
        if not payment:
            log_error("click", "order_not_found",
                      f"Order not found: {merchant_trans_id}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ERROR_ORDER_NOT_FOUND,
                "Order not found"
            )

        # 3. Allaqachon to'langan-mi?
        if is_payment_already_completed(merchant_trans_id):
            log_error("click", "already_paid",
                      f"Order already paid: {merchant_trans_id}",
                      order_id=merchant_trans_id)
            return self._error_response(
                data, CLICK_ERROR_ALREADY_PAID,
                "Already paid"
            )

        # 4. Status cancelled-mi?
        if payment.get("payment_status") == "failed":
            return self._error_response(
                data, CLICK_ERROR_ORDER_CANCELLED,
                "Transaction cancelled"
            )

        # 5. Summani tekshirish
        expected_amount = float(payment.get("amount", 0))
        received_amount = float(amount)
        if abs(expected_amount - received_amount) > 0.01:
            log_error("click", "amount_mismatch",
                      f"Expected: {expected_amount}, Got: {received_amount}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ERROR_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        # ✅ Prepare muvaffaqiyatli — click_trans_id ni saqlash
        update_click_payment_status(
            merchant_trans_id, "preparing",
            click_trans_id=click_trans_id
        )

        log_transaction("click", merchant_trans_id, "prepared",
                        received_amount, click_trans_id)

        # Click requires merchant_prepare_id in response. 
        # We must return the same ID we saved (the payment['id']) for consistency.
        response = {
            "click_trans_id": int(click_trans_id),
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": payment.get("id"), 
            "error": CLICK_ERROR_SUCCESS,
            "error_note": "Success",
        }

        log_callback("click", "prepare", data, response)
        return response

    def _handle_complete(self, data: dict) -> Dict[str, Any]:
        """
        Complete callback — to'lovni yakunlash yoki bekor qilish.
        Click bu so'rovni to'lov muvaffaqiyatli/muvaffaqiyatsiz bo'lganda yuboradi.

        Tekshiruvlar:
        1. Signature tekshirish
        2. Buyurtma mavjudligini tekshirish
        3. Allaqachon to'langanligini tekshirish
        4. Click error parametri tekshirish (0=success, <0=error)
        """
        from modules.payment import (
            get_payment_by_order_id, is_payment_already_completed,
            update_click_payment_status
        )

        click_trans_id = str(data.get("click_trans_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = data.get("amount", "0")
        error = int(data.get("error", 0))

        # 1. Signature tekshirish
        if not self.verify_signature(data, 1):
            return self._error_response(
                data, CLICK_ERROR_SIGN_CHECK_FAILED,
                "SIGN CHECK FAILED!"
            )

        # 2. Buyurtma mavjudligini tekshirish
        payment = get_payment_by_order_id(merchant_trans_id)
        if not payment:
            log_error("click", "order_not_found",
                      f"Order not found on complete: {merchant_trans_id}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ERROR_ORDER_NOT_FOUND,
                "Order not found"
            )

        # 3. Allaqachon to'langan-mi?
        if is_payment_already_completed(merchant_trans_id):
            log_error("click", "already_paid",
                      f"Order already completed: {merchant_trans_id}",
                      order_id=merchant_trans_id)
            return self._error_response(
                data, CLICK_ERROR_ALREADY_PAID,
                "Already paid"
            )

        # 4. Click xatolik yuborgan bo'lsa → bekor qilish
        if error < 0:
            update_click_payment_status(
                merchant_trans_id, "failed",
                click_trans_id=click_trans_id
            )
            log_transaction("click", merchant_trans_id, "cancelled",
                            float(amount), click_trans_id,
                            details={"click_error": error})

            response = {
                "click_trans_id": int(click_trans_id),
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": payment.get("id", merchant_trans_id),
                "error": CLICK_ERROR_ORDER_CANCELLED,
                "error_note": "Transaction cancelled",
            }
            log_callback("click", "complete_cancel", data, response)
            return response

        # 5. Summani tekshirish
        expected_amount = float(payment.get("amount", 0))
        received_amount = float(amount)
        if abs(expected_amount - received_amount) > 0.01:
            log_error("click", "amount_mismatch",
                      f"Complete amount mismatch: expected={expected_amount}, "
                      f"got={received_amount}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ERROR_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        # ✅ To'lov muvaffaqiyatli!
        update_click_payment_status(
            merchant_trans_id, "success",
            click_trans_id=click_trans_id
        )

        log_transaction("click", merchant_trans_id, "completed",
                        received_amount, click_trans_id)

        response = {
            "click_trans_id": int(click_trans_id),
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": merchant_trans_id,  # using order_id as confirm_id
            "error": CLICK_ERROR_SUCCESS,
            "error_note": "Success",
        }

        log_callback("click", "complete_success", data, response)
        return response

    def _error_response(self, data: dict, error_code: int,
                        error_note: str) -> dict:
        """Click xatolik javobini yaratish."""
        click_trans_id = data.get("click_trans_id", 0)
        merchant_trans_id = data.get("merchant_trans_id", "")

        return {
            "click_trans_id": int(click_trans_id) if click_trans_id else 0,
            "merchant_trans_id": str(merchant_trans_id),
            "error": error_code,
            "error_note": error_note,
        }


# ── Singleton instance ──
click_provider = ClickPaymentProvider()
