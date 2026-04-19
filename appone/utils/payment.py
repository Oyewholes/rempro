import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def calculate_payment_breakdown(amount, contract):
    """Calculate payment breakdown with taxes."""
    platform_tax = (amount * contract.platform_tax_rate) / 100
    dwelling_tax = (amount * contract.dwelling_country_tax_rate) / 100
    work_tax = (amount * contract.work_country_tax_rate) / 100

    total_tax = platform_tax + dwelling_tax + work_tax
    net_amount = amount - total_tax

    return {
        "gross_amount": float(amount),
        "platform_tax": float(platform_tax),
        "dwelling_country_tax": float(dwelling_tax),
        "work_country_tax": float(work_tax),
        "total_tax": float(total_tax),
        "net_amount": float(net_amount),
        "breakdown": {
            f"Platform Fee ({contract.platform_tax_rate}%)": float(platform_tax),
            f"Dwelling Country Tax ({contract.dwelling_country_tax_rate}%)": float(
                dwelling_tax
            ),
            f"Work Country Tax ({contract.work_country_tax_rate}%)": float(work_tax),
        },
    }


def process_paystack_payment(payment):
    """Process payment via Paystack."""
    try:
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        freelancer_email = payment.contract.freelancer.paystack_email
        data = {
            "email": freelancer_email,
            "amount": int(payment.net_amount * 100),  # kobo/cents
            "reference": payment.transaction_reference,
            "currency": payment.currency,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback",
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as exc:
        logger.error("process_paystack_payment error: %s", exc)
        return None
