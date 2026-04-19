# Serializers package — re-exports every serializer class so that
# existing imports of the form `from appone.serializers import X` keep working.

from .auth import RegisterSerializer, LoginSerializer, LogoutSerializer
from .user import UserInfoSerializer
from .otp import (
    OTPVerificationSerializer,
    OTPValidateSerializer,
    AdminVerificationSerializer,
    SendPhoneOTPSerializer,
)
from .freelancer import (
    FreelancerProfileSerializer,
    FreelancerProfileUpdateSerializer,
    FreelancerPublicProfileSerializer,
    AddNINSerializer,
    AddPortfolioSerializer,
    AddBankingDetailsSerializer,
)
from .company import (
    CompanyProfileSerializer,
    CompanyProfileUpdateSerializer,
    ScheduleMeetingSerializer,
    VerifyCompanyRegistrationSerializer,
)
from .job import (
    JobPostingSerializer,
    JobApplicationSerializer,
    HireFreelancerSerializer,
    UpdateJobApplicationStatusSerializer,
)
from .contract import ContractSerializer, PaymentSerializer
from .workspace import (
    WorkspaceSerializer,
    TaskSerializer,
    MessageSerializer,
    ProfileAccessLogSerializer,
    UpdateTaskStatusSerializer,
)

__all__ = [
    # Auth
    'RegisterSerializer',
    'LoginSerializer',
    'LogoutSerializer',
    # User
    'UserInfoSerializer',
    # OTP / Admin
    'OTPVerificationSerializer',
    'OTPValidateSerializer',
    'AdminVerificationSerializer',
    'SendPhoneOTPSerializer',
    # Freelancer
    'FreelancerProfileSerializer',
    'FreelancerProfileUpdateSerializer',
    'FreelancerPublicProfileSerializer',
    'AddNINSerializer',
    'AddPortfolioSerializer',
    'AddBankingDetailsSerializer',
    # Company
    'CompanyProfileSerializer',
    'CompanyProfileUpdateSerializer',
    'ScheduleMeetingSerializer',
    'VerifyCompanyRegistrationSerializer',
    # Jobs
    'JobPostingSerializer',
    'JobApplicationSerializer',
    'HireFreelancerSerializer',
    'UpdateJobApplicationStatusSerializer',
    # Contracts & Payments
    'ContractSerializer',
    'PaymentSerializer',
    # Workspace
    'WorkspaceSerializer',
    'TaskSerializer',
    'MessageSerializer',
    'ProfileAccessLogSerializer',
    'UpdateTaskStatusSerializer',
]
