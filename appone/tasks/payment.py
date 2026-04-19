from celery import shared_task
from django.utils import timezone
from appone.models import Payment
from appone.utils import process_paystack_payment, send_notification_email
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_payment_task(payment_id):
    """Async task to process payment via Paystack."""
    try:
        payment = Payment.objects.get(id=payment_id)

        if payment.status != "pending":
            return {"success": False, "error": "Payment already processed"}

        payment.status = "processing"
        payment.save()

        result = process_paystack_payment(payment)

        if result and result.get("status"):
            payment.status = "completed"
            payment.processed_at = timezone.now()
            payment.save()

            freelancer = payment.contract.freelancer
            send_notification_email(
                freelancer.user.email,
                "Payment Received",
                (
                    f"Dear {freelancer.first_name}, you have received a payment of "
                    f"{payment.net_amount} {payment.currency}."
                ),
            )

            company = payment.contract.company
            send_notification_email(
                company.company_email,
                "Payment Processed",
                (
                    f"Your payment of {payment.amount} {payment.currency} "
                    "has been processed successfully."
                ),
            )

            return {"success": True, "payment_id": str(payment_id)}
        else:
            payment.status = "failed"
            payment.save()
            return {"success": False, "error": "Payment processing failed"}

    except Payment.DoesNotExist:
        return {"success": False, "error": "Payment not found"}


@shared_task
def generate_monthly_payment_reports():
    """Generate monthly payment reports for accounting."""
    from datetime import date

    current_month = timezone.now().month
    current_year = timezone.now().year

    payments = Payment.objects.filter(
        status="completed",
        payment_date__month=current_month,
        payment_date__year=current_year,
    )

    total_amount = sum(p.amount for p in payments)
    total_platform_tax = sum(p.platform_tax for p in payments)
    total_dwelling_tax = sum(p.dwelling_country_tax for p in payments)
    total_work_tax = sum(p.work_country_tax for p in payments)

    report = {
        "month": current_month,
        "year": current_year,
        "total_transactions": payments.count(),
        "total_amount": float(total_amount),
        "total_platform_tax": float(total_platform_tax),
        "total_dwelling_tax": float(total_dwelling_tax),
        "total_work_tax": float(total_work_tax),
    }

    send_notification_email(
        "admin@virtualcitizenship.com",
        f"Monthly Payment Report - {date.today().strftime('%B %Y')}",
        f"Payment Report:\n{report}",
    )

    return report
