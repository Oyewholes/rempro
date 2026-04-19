from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from appone.models import Message, Contract
from appone.utils import flag_suspicious_message, send_notification_email
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_flagged_messages():
    """Periodic task to check and flag suspicious messages."""
    recent_messages = Message.objects.filter(
        flagged=False, created_at__gte=timezone.now() - timedelta(hours=1)
    )

    flagged_count = 0
    for message in recent_messages:
        is_flagged, reason = flag_suspicious_message(message.content)
        if is_flagged:
            message.flagged = True
            message.flag_reason = reason
            message.save()
            flagged_count += 1

            send_notification_email(
                "admin@virtualcitizenship.com",
                "Suspicious Message Detected",
                (
                    f"Message ID: {message.id}\n"
                    f"Workspace: {message.workspace.name}\n"
                    f"Reason: {reason}"
                ),
            )

    return {"checked": recent_messages.count(), "flagged": flagged_count}


@shared_task
def send_contract_expiry_notifications():
    """Periodic task to notify about expiring contracts."""
    expiring_soon = Contract.objects.filter(
        status="active",
        end_date__lte=timezone.now() + timedelta(days=7),
        end_date__gte=timezone.now(),
    )

    notified_count = 0
    for contract in expiring_soon:
        send_notification_email(
            contract.freelancer.user.email,
            "Contract Expiring Soon",
            (
                f"Dear {contract.freelancer.first_name}, your contract with "
                f"{contract.company.company_name} will expire on {contract.end_date}."
            ),
        )
        send_notification_email(
            contract.company.company_email,
            "Contract Expiring Soon",
            (
                f"Your contract with {contract.freelancer.first_name} "
                f"{contract.freelancer.last_name} will expire on {contract.end_date}."
            ),
        )
        notified_count += 1

    return {"notified": notified_count}
