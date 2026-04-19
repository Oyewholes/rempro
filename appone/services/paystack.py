# appone/services/paystack.py  (skeleton — read-only, not written to codebase)
import requests
from django.conf import settings

PAYSTACK_BASE = "https://api.paystack.co"


class PaystackService:
    def __init__(self):
        self.secret = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json",
        }

    def _post(self, path, payload):
        r = requests.post(
            f"{PAYSTACK_BASE}{path}",
            json=payload,
            headers=self.headers,
        )
        r.raise_for_status()
        return r.json()

    def _get(self, path):
        r = requests.get(f"{PAYSTACK_BASE}{path}", headers=self.headers)
        r.raise_for_status()
        return r.json()

    # ── Charging the company ──────────────────────────────────────────────
    def initialize_transaction(
        self,
        email,
        amount_kobo,
        reference,
        metadata=None,
    ):
        return self._post(
            "/transaction/initialize",
            {
                "email": email,
                "amount": amount_kobo,
                "reference": reference,
                "metadata": metadata or {},
            },
        )

    def verify_transaction(self, reference):
        return self._get(f"/transaction/verify/{reference}")

    # ── Paying the freelancer ─────────────────────────────────────────────
    def create_transfer_recipient(
        self, name, account_number, bank_code, currency="NGN"
    ):
        return self._post(
            "/transferrecipient",
            {
                "type": "nuban",
                "name": name,
                "account_number": account_number,
                "bank_code": bank_code,
                "currency": currency,
            },
        )

    def initiate_transfer(
        self,
        amount_kobo,
        recipient_code,
        reason,
        reference,
    ):
        return self._post(
            "/transfer",
            {
                "source": "balance",
                "amount": amount_kobo,
                "recipient": recipient_code,
                "reason": reason,
                "reference": reference,
            },
        )

    def verify_transfer(self, transfer_code):
        return self._get(f"/transfer/{transfer_code}")
