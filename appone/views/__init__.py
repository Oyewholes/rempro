# Views package — re-exports every ViewSet so that existing imports
# of the form `from appone.views import X` keep working.

from .auth import AuthViewSet
from .otp import OTPViewSet
from .freelancer_profile import FreelancerProfileViewSet
from .company_profile import CompanyProfileViewSet
from .job_posting import JobPostingViewSet
from .job_application import JobApplicationViewSet
from .contract import ContractViewSet
from .workspace import WorkspaceViewSet
from .task import TaskViewSet
from .message import MessageViewSet
from .payment import PaymentViewSet
from .admin import AdminViewSet

__all__ = [
    'AuthViewSet',
    'OTPViewSet',
    'FreelancerProfileViewSet',
    'CompanyProfileViewSet',
    'JobPostingViewSet',
    'JobApplicationViewSet',
    'ContractViewSet',
    'WorkspaceViewSet',
    'TaskViewSet',
    'MessageViewSet',
    'PaymentViewSet',
    'AdminViewSet',
]