# appone/utils/tax.py  (read-only plan)
from decimal import ROUND_DOWN, Decimal

from django.conf import settings


def calculate_tax_split(gross_amount: Decimal, contract=None) -> dict:
    """
    Returns a breakdown dict:
    {
        "gross":          Decimal,
        "platform_charge": Decimal,
        "home_tax":       Decimal,
        "work_tax":       Decimal,
        "total_deductions": Decimal,
        "net_to_freelancer": Decimal,
        "rates": {
            "platform_pct": Decimal,
            "home_tax_pct": Decimal,
            "work_tax_pct": Decimal,
        },
        "countries": {
            "home": {"name": str, "code": str},
            "work": {"name": str, "code": str},
        }
    }

    If `contract` is provided and its tax rate fields are non-zero,
    those override the env defaults (per-contract customisation).
    """
    TWO_PLACES = Decimal("0.01")

    # Resolve rates: contract overrides env defaults
    platform_pct = (
        contract.platform_tax_rate
        if contract and contract.platform_tax_rate
        else settings.PLATFORM_CHARGE_PERCENT
    )
    home_pct = (
        contract.dwelling_country_tax_rate
        if contract and contract.dwelling_country_tax_rate
        else settings.HOME_COUNTRY_TAX_PERCENT
    )
    work_pct = (
        contract.work_country_tax_rate
        if contract and contract.work_country_tax_rate
        else settings.WORK_COUNTRY_TAX_PERCENT
    )

    platform_charge = (gross_amount * platform_pct / 100).quantize(
        TWO_PLACES, ROUND_DOWN
    )
    home_tax = (gross_amount * home_pct / 100).quantize(TWO_PLACES, ROUND_DOWN)
    work_tax = (gross_amount * work_pct / 100).quantize(TWO_PLACES, ROUND_DOWN)
    total_deductions = platform_charge + home_tax + work_tax
    net_to_freelancer = gross_amount - total_deductions

    return {
        "gross": gross_amount,
        "platform_charge": platform_charge,
        "home_tax": home_tax,
        "work_tax": work_tax,
        "total_deductions": total_deductions,
        "net_to_freelancer": net_to_freelancer,
        "rates": {
            "platform_pct": platform_pct,
            "home_tax_pct": home_pct,
            "work_tax_pct": work_pct,
        },
        "countries": {
            "home": {
                "name": settings.HOME_COUNTRY_NAME,
                "code": settings.HOME_COUNTRY_CODE,
            },
            "work": {
                "name": settings.WORK_COUNTRY_NAME,
                "code": settings.WORK_COUNTRY_CODE,
            },
        },
    }
