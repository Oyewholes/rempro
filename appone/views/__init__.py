# Views package — re-exports every ViewSet so that existing imports
# of the form `from appone.views import X` keep working.

from .admin import AdminViewSet
from .auth import AuthViewSet
from .company_profile import CompanyProfileViewSet
from .contract import ContractViewSet
from .freelancer_profile import FreelancerProfileViewSet
from .job_application import JobApplicationViewSet
from .job_posting import JobPostingViewSet
from .message import MessageViewSet
from .otp import OTPViewSet
from .payment import PaymentViewSet, PaystackWebhookView
from .task import TaskViewSet
from .workspace import WorkspaceViewSet

__all__ = [
    "AuthViewSet",
    "OTPViewSet",
    "FreelancerProfileViewSet",
    "CompanyProfileViewSet",
    "JobPostingViewSet",
    "JobApplicationViewSet",
    "ContractViewSet",
    "WorkspaceViewSet",
    "TaskViewSet",
    "MessageViewSet",
    "PaymentViewSet",
    "AdminViewSet",
    "PaystackWebhookView",
]
