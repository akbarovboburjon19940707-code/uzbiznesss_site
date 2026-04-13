"""
Payme Payment Provider — Production Integration
=======================================
Payme tizimi JSON-RPC orqali ishlaydi. Hamma requestlar Basic Auth bilan tekshiriladi.
Payme docs: https://developer.payme.uz/
"""
import os
import base64
import logging
from typing import Dict, Any
from datetime import datetime

from modules.payment_service import PaymentProvider, PaymentError
from modules.payment_logger import log_callback, log_transaction, log_error

logger = logging.getLogger(__name__)

PAYME_MERCHANT_ID = os.environ.get("PAYME_MERCHANT_ID", "")
PAYME_KEY = os.environ.get("PAYME_KEY", "")

# Payme Error Codes
PAYME_ERROR_INTERNAL_SYSTEM = -32400
PAYME_ERROR_INSUFFICIENT_PRIVILEGE = -32504
PAYME_ERROR_INVALID_JSON_RPC_OBJECT = -32600
PAYME_ERROR_METHOD_NOT_FOUND = -32601
PAYME_ERROR_INVALID_AMOUNT = -31001
PAYME_ERROR_TRANSACTION_NOT_FOUND = -31003
PAYME_ERROR_INVALID_ACCOUNT = -31050
PAYME_ERROR_CANT_CANCEL_TRANSACTION = -31007
PAYME_ERROR_ORDER_FOUND = -31099

PAYME_PAYMENT_URL = "https://checkout.paycom.uz"

class PaymePaymentProvider(PaymentProvider):
    @property
    def provider_name(self) -> str:
        return "payme"

    def create_payment_url(self, order_id: str, amount: float, return_url: str = "") -> str:
        # Check if PAYME_MERCHANT_ID is available
        if not PAYME_MERCHANT_ID:
            raise PaymentError(
                "Payme credentials sozlanmagan",
                error_code=-100,
                details={"missing": "PAYME_MERCHANT_ID"}
            )
            
        tiyins = int(amount * 100)
        params_str = f"m={PAYME_MERCHANT_ID};ac.order_id={order_id};a={tiyins}"
        if return_url:
            params_str += f";c={return_url}"
            
        encoded = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')
        url = f"{PAYME_PAYMENT_URL}/{encoded}"
        
        log_transaction("payme", order_id, "url_created", amount, details={"payment_url": url})
        return url

    def verify_callback(self, data: dict) -> Dict[str, Any]:
        return {"success": True}

    def handle_callback(self, data: dict, auth_header: str = None) -> Dict[str, Any]:
        req_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})
        
        if not auth_header or not auth_header.startswith("Basic "):
            return self._error_response(req_id, PAYME_ERROR_INSUFFICIENT_PRIVILEGE, "Auth failed")
            
        try:
            auth_decoded = base64.b64decode(auth_header.split(" ")[1]).decode("utf-8")
        except Exception:
            return self._error_response(req_id, PAYME_ERROR_INSUFFICIENT_PRIVILEGE, "Auth decode failed")
            
        if ":" not in auth_decoded:
             return self._error_response(req_id, PAYME_ERROR_INSUFFICIENT_PRIVILEGE, "Auth format err")
             
        _, password = auth_decoded.split(":", 1)
        if password != PAYME_KEY and PAYME_KEY != "":
            return self._error_response(req_id, PAYME_ERROR_INSUFFICIENT_PRIVILEGE, "Invalid auth")
            
        if method == "CheckPerformTransaction":
            return self._handle_check_perform_transaction(req_id, params)
        elif method == "CreateTransaction":
            return self._handle_create_transaction(req_id, params)
        elif method == "PerformTransaction":
            return self._handle_perform_transaction(req_id, params)
        elif method == "CancelTransaction":
            return self._handle_cancel_transaction(req_id, params)
        elif method == "CheckTransaction":
            return self._handle_check_transaction(req_id, params)
        else:
            return self._error_response(req_id, PAYME_ERROR_METHOD_NOT_FOUND, f"Method not found: {method}")

    def _handle_check_perform_transaction(self, req_id, params):
        from modules.payment import get_payment_by_order_id
        
        account = params.get("account", {})
        order_id = account.get("order_id")
        amount = params.get("amount", 0)
        
        if not order_id:
            return self._error_response(req_id, PAYME_ERROR_INVALID_ACCOUNT, "order_id topilmadi")
            
        payment = get_payment_by_order_id(order_id)
        if not payment:
            return self._error_response(req_id, PAYME_ERROR_INVALID_ACCOUNT, "Buyurtma topilmadi")
            
        expected_amount = int(float(payment.get("amount", 0)) * 100)
        if expected_amount != amount:
            return self._error_response(req_id, PAYME_ERROR_INVALID_AMOUNT, "Noto'g'ri summa")
            
        if payment.get("payment_status") == "success":
             return self._error_response(req_id, PAYME_ERROR_ORDER_FOUND, "Allaqachon to'langan")
             
        return self._success_response(req_id, {"allow": True})

    def _handle_create_transaction(self, req_id, params):
        from modules.payment import (
             get_payment_by_order_id, 
             update_payme_payment_status, 
             get_payment_by_payme_trans_id
        )

        trans_id = params.get("id")
        account = params.get("account", {})
        order_id = account.get("order_id")
        amount = params.get("amount", 0)
        
        payment_by_trans = get_payment_by_payme_trans_id(trans_id)
        if payment_by_trans:
            state = 1 if payment_by_trans.get("payment_status") != "success" else 2
            if state == 1 and payment_by_trans.get("payment_status") == "failed":
                state = -1
                
            return self._success_response(req_id, {
                "create_time": int(payment_by_trans.get("payme_create_time", datetime.now().timestamp() * 1000)),
                "transaction": payment_by_trans.get("order_id"),
                "state": state
            })
            
        payment = get_payment_by_order_id(order_id)
        if not payment:
            return self._error_response(req_id, PAYME_ERROR_INVALID_ACCOUNT, "Buyurtma topilmadi")
            
        expected_amount = int(float(payment.get("amount", 0)) * 100)
        if expected_amount != amount:
            return self._error_response(req_id, PAYME_ERROR_INVALID_AMOUNT, "Noto'g'ri summa")
            
        create_time = int(datetime.now().timestamp() * 1000)
        update_payme_payment_status(order_id, "preparing", trans_id, create_time=create_time)
        
        return self._success_response(req_id, {
            "create_time": create_time,
            "transaction": order_id,
            "state": 1
        })

    def _handle_perform_transaction(self, req_id, params):
        from modules.payment import get_payment_by_payme_trans_id, update_payme_payment_status
        
        trans_id = params.get("id")
        payment = get_payment_by_payme_trans_id(trans_id)
        
        if not payment:
            return self._error_response(req_id, PAYME_ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
            
        if payment.get("payment_status") == "success":
            return self._success_response(req_id, {
                "transaction": payment.get("order_id"),
                "perform_time": int(payment.get("payme_perform_time", datetime.now().timestamp() * 1000)),
                "state": 2
            })
            
        perform_time = int(datetime.now().timestamp() * 1000)
        update_payme_payment_status(payment.get("order_id"), "success", trans_id, perform_time=perform_time)
        log_transaction("payme", payment.get("order_id"), "completed", float(payment.get("amount", 0)), trans_id)
        
        return self._success_response(req_id, {
            "transaction": payment.get("order_id"),
            "perform_time": perform_time,
            "state": 2
        })

    def _handle_cancel_transaction(self, req_id, params):
        from modules.payment import get_payment_by_payme_trans_id, update_payme_payment_status
        
        trans_id = params.get("id")
        reason = params.get("reason")
        payment = get_payment_by_payme_trans_id(trans_id)
        
        if not payment:
            return self._error_response(req_id, PAYME_ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
            
        if payment.get("payment_status") == "success":
             return self._error_response(req_id, PAYME_ERROR_CANT_CANCEL_TRANSACTION, "Yakunlangan to'lovni bekor qilib bo'lmaydi")
             
        cancel_time = int(datetime.now().timestamp() * 1000)
        update_payme_payment_status(payment.get("order_id"), "failed", trans_id, cancel_time=cancel_time, reason=reason)
        
        return self._success_response(req_id, {
            "transaction": payment.get("order_id"),
            "cancel_time": cancel_time,
            "state": -1
        })
        
    def _handle_check_transaction(self, req_id, params):
        from modules.payment import get_payment_by_payme_trans_id
        
        trans_id = params.get("id")
        payment = get_payment_by_payme_trans_id(trans_id)
        
        if not payment:
             return self._error_response(req_id, PAYME_ERROR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")
             
        status = payment.get("payment_status")
        if status == "success":
            state = 2
        elif status == "failed":
            state = -1
        else:
            state = 1
            
        return self._success_response(req_id, {
            "create_time": int(payment.get("payme_create_time", 0)),
            "perform_time": int(payment.get("payme_perform_time", 0)),
            "cancel_time": int(payment.get("payme_cancel_time", 0)),
            "transaction": payment.get("order_id"),
            "state": state,
            "reason": payment.get("payme_cancel_reason", None)
        })

    def _success_response(self, req_id, result):
        return {"result": result, "id": req_id}

    def _error_response(self, req_id, code, message):
        return {
            "error": {
                "code": code,
                "message": {"ru": message, "uz": message, "en": message}
            },
            "id": req_id
        }

payme_provider = PaymePaymentProvider()

