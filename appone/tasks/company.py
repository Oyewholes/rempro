from celery import shared_task
from appone.models import CompanyProfile
from appone.utils import verify_company_registration, send_notification_email
import logging

logger = logging.getLogger(__name__)


@shared_task
def verify_company_registration_task(company_id):
    """Async task to verify company registration with government API."""
    try:
        company = CompanyProfile.objects.get(id=company_id)
        result = verify_company_registration(
            company.company_registration_number, company.country
        )

        if result and result.get("verified"):
            company.api_verification_status = True
            company.api_verification_data = result
            company.save()

            send_notification_email(
                company.company_email,
                "Company Verification Successful",
                f"Your company {company.company_name} has been successfully verified.",
            )

        return {
            "success": True,
            "verified": result.get("verified", False) if result else False,
        }
    except CompanyProfile.DoesNotExist:
        return {"success": False, "error": "Company not found"}
