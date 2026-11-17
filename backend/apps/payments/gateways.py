"""Payment gateway adapters. No raw card data is ever stored."""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayNotConfigured(Exception):
    pass


class GatewayError(Exception):
    pass


class MpesaDarajaClient:
    """Safaricom Daraja STK Push adapter.

    Credentials come exclusively from environment configuration. When they are
    absent the adapter raises GatewayNotConfigured instead of pretending a
    payment was made.
    """

    def __init__(self):
        self.consumer_key = settings.M_PESA_CONSUMER_KEY
        self.consumer_secret = settings.M_PESA_CONSUMER_SECRET
        self.shortcode = settings.M_PESA_SHORTCODE
        self.passkey = settings.M_PESA_PASSKEY
        self.callback_url = settings.M_PESA_CALLBACK_URL
        self.env = settings.M_PESA_ENV

    @property
    def configured(self):
        return bool(self.consumer_key and self.consumer_secret and self.shortcode and self.passkey)

    @property
    def base_url(self):
        return "https://sandbox.safaricom.co.ke" if self.env == "sandbox" else "https://api.safaricom.co.ke"

    def _token(self):
        if not self.configured:
            raise GatewayNotConfigured("M-Pesa Daraja credentials are not configured.")
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        creds = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                return data["access_token"]
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise GatewayError(f"Unable to obtain M-Pesa token: {exc}") from exc

    def stk_push(self, phone, amount, account_reference, description):
        token = self._token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": description[:13],
        }
        req = urllib.request.Request(
            f"{self.base_url}/mpesa/stkpush/v1/processrequest",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise GatewayError(f"M-Pesa STK push failed: {body}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"M-Pesa STK push failed: {exc}") from exc

    def query(self, checkout_request_id):
        token = self._token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        req = urllib.request.Request(
            f"{self.base_url}/mpesa/stkpushquery/v1/query",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise GatewayError(f"M-Pesa query failed: {exc}") from exc


def normalize_phone(phone):
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    return digits


class FlutterwaveCardGateway:
    """Flutterwave hosted-checkout card adapter.

    Follows the same contract as ``MpesaDarajaClient``: never fabricate a
    successful payment, and always re-verify with the provider before marking a
    payment successful.
    """

    def __init__(self):
        self.secret_key = settings.FLW_SECRET_KEY
        self.env = settings.FLW_ENV

    @property
    def configured(self):
        return bool(self.secret_key)

    @property
    def base_url(self):
        return "https://api.flutterwave.com/v3"

    def _headers(self):
        return {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"}

    def initiate(self, amount, currency, tx_ref, redirect_url, email, name, phone=""):
        if not self.configured:
            raise GatewayNotConfigured("Card gateway credentials are not configured.")
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),
            "currency": currency,
            "redirect_url": redirect_url,
            "payment_options": "card",
            "customer": {"email": email, "name": name, "phonenumber": phone},
            "meta": {"reason": "Insurance premium"},
        }
        req = urllib.request.Request(
            f"{self.base_url}/payments",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise GatewayError(f"Flutterwave initiate failed: {body}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"Flutterwave unreachable: {exc}") from exc
        if data.get("status") != "success" or not data.get("data", {}).get("link"):
            raise GatewayError(data.get("message", "Flutterwave initiate failed"))
        return data["data"]["link"]

    def verify(self, tx_ref):
        if not self.configured:
            raise GatewayNotConfigured("Card gateway credentials are not configured.")
        req = urllib.request.Request(
            f"{self.base_url}/transactions/verify_by_reference?tx_ref={urllib.parse.quote(tx_ref)}",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            raise GatewayError(f"Flutterwave verify failed: {body}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"Flutterwave unreachable: {exc}") from exc
