import requests
from django.conf import settings


def create_paystack_subaccount(business_name, bank_code, account_number):
    """
    Creates a Paystack subaccount and returns the subaccount_code.
    """
    url = "https://api.paystack.co/subaccount"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "business_name": business_name,
        "settlement_bank": bank_code,
        "account_number": account_number,
        "percentage_charge": 0.0,
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        if response.status_code in [200, 201] and response_data.get("status"):
            return response_data["data"]["subaccount_code"]
        else:
            return None
    except Exception:
        return None


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


def process_paystack_payment(
    payment, work_country_code=None, dwelling_country_code=None
):
    """Process payment via Paystack Dynamic Split."""
    try:
        from appone.models.payment import CountryTaxAccount

        contract = payment.contract
        company = contract.company
        freelancer = contract.freelancer

        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        customer_email = company.user.email
        base_amount = float(payment.amount)
        flat_fee = 100 if base_amount >= 2500 else 0
        charge_amount = (base_amount + flat_fee) / (1 - 0.015)
        paystack_fee = charge_amount - base_amount
        if paystack_fee > 2000:
            charge_amount = base_amount + 2000
        gross_amount_kobo = int(charge_amount * 100)

        data = {
            "email": customer_email,
            "amount": gross_amount_kobo,
            "reference": payment.transaction_reference,
            "currency": payment.currency,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback",
        }
        subaccounts = []

        if freelancer.paystack_subaccount_code:
            total_tax_rate = (
                contract.platform_tax_rate
                + contract.dwelling_country_tax_rate
                + contract.work_country_tax_rate
            )
            freelancer_share = float(100 - total_tax_rate)

            subaccounts.append(
                {
                    "subaccount": freelancer.paystack_subaccount_code,
                    "share": freelancer_share,
                }
            )
        if work_country_code:
            work_tax_acct = CountryTaxAccount.objects.filter(
                country_name__icontains=work_country_code
            ).first()
            if work_tax_acct and work_tax_acct.paystack_subaccount_code:
                subaccounts.append(
                    {
                        "subaccount": work_tax_acct.paystack_subaccount_code,
                        "share": float(contract.work_country_tax_rate),
                    }
                )
        if dwelling_country_code:
            dwell_tax_acct = CountryTaxAccount.objects.filter(
                country_name__icontains=dwelling_country_code
            ).first()
            if dwell_tax_acct and dwell_tax_acct.paystack_subaccount_code:
                subaccounts.append(
                    {
                        "subaccount": dwell_tax_acct.paystack_subaccount_code,
                        "share": float(contract.dwelling_country_tax_rate),
                    }
                )
        if subaccounts:
            data["split"] = {
                "type": "percentage",
                "bearer": "account",
                "subaccounts": subaccounts,
            }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()

        return None
    except Exception:
        return None
