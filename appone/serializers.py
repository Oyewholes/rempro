from rest_framework import serializers
from .models import (
    User, FreelancerProfile, CompanyProfile, OTPVerification,
    JobPosting, JobApplication, Contract, Payment,
    Workspace, Task, Message, ProfileAccessLog
)
from django.db import transaction
from django.utils import timezone


# --- 1. Authentication and User Serializers ---

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('id', 'email', 'user_type', 'password', 'password2')
        read_only_fields = ('id',)

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            user_type=validated_data['user_type']
        )
        # Create corresponding profile immediately
        if user.user_type == 'freelancer':
            FreelancerProfile.objects.create(user=user)
        elif user.user_type == 'company':
            CompanyProfile.objects.create(user=user)

        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


# --- 2. OTP and Verification Serializers ---

class OTPVerificationSerializer(serializers.ModelSerializer):
    """Serializer for requesting a new OTP."""

    class Meta:
        model = OTPVerification
        # Fields for creation: user, type, and contact info (phone or email)
        fields = ('id', 'user', 'otp_type', 'phone_number', 'email', 'expires_at')
        read_only_fields = ('id', 'expires_at')

    def validate(self, data):
        # Ensure only one of phone_number or email is provided based on otp_type
        if data['otp_type'] == 'phone' and not data.get('phone_number'):
            raise serializers.ValidationError("Phone number is required for phone verification.")
        if data['otp_type'] != 'phone' and not data.get('email'):
            raise serializers.ValidationError("Email is required for this type of verification.")

        # Set expiry time to 10 minutes from now (assuming common flow)
        data['expires_at'] = timezone.now() + timezone.timedelta(minutes=10)
        return data


class OTPValidateSerializer(serializers.Serializer):
    """Serializer for validating an existing OTP."""
    otp_code = serializers.CharField(max_length=6, required=True)
    contact_info = serializers.CharField(required=True, help_text="The phone number or email used for the OTP.")


class AdminVerificationSerializer(serializers.Serializer):
    """Serializer for admin to verify/reject a profile."""
    verification_status = serializers.ChoiceField(choices=[('verified', 'Verified'), ('rejected', 'Rejected')])
    # Optional field for rejection reason or other notes
    notes = serializers.CharField(required=False, allow_blank=True)


class ScheduleMeetingSerializer(serializers.Serializer):
    """Serializer for admin to schedule a verification meeting for a company."""
    meeting_scheduled_at = serializers.DateTimeField()
    meeting_link = serializers.URLField(max_length=500)


# --- 3. Profile Serializers ---

# Helper Serializer for User's public details
class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'user_type', 'is_verified')
        read_only_fields = fields


# --- Freelancer Profile ---

class FreelancerProfileSerializer(serializers.ModelSerializer):
    """Comprehensive Serializer for Freelancer profile creation/detail (Private View)."""
    user = UserInfoSerializer(read_only=True)

    class Meta:
        model = FreelancerProfile
        exclude = ('admin_verified_by',)
        read_only_fields = ('user', 'digital_id', 'digital_id_link', 'id_card_image',
                            'verification_status', 'profile_completion_percentage',
                            'created_at', 'updated_at', 'admin_verified_at')


class FreelancerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating common freelancer fields."""

    class Meta:
        model = FreelancerProfile
        fields = (
            'first_name', 'last_name', 'phone_number', 'nin',
            'cv_file', 'live_photo', 'portfolio_files', 'bio',
            'skills', 'paystack_email', 'payoneer_email', 'approved_countries'
        )


class FreelancerPublicProfileSerializer(serializers.ModelSerializer):
    """Minimal Serializer for viewing by Company (Public View)."""
    user_id = serializers.ReadOnlyField(source='user.id')

    class Meta:
        model = FreelancerProfile
        fields = (
            'user_id', 'first_name', 'last_name', 'skills', 'bio',
            'verification_status', 'digital_id', 'profile_completion_percentage'
        )
        read_only_fields = fields


# --- Company Profile ---

class CompanyProfileSerializer(serializers.ModelSerializer):
    """Comprehensive Serializer for Company profile creation/detail (Private View)."""
    user = UserInfoSerializer(read_only=True)

    class Meta:
        model = CompanyProfile
        exclude = ('verified_by', 'api_verification_data')
        read_only_fields = ('user', 'verification_status', 'api_verification_status',
                            'verified_at', 'created_at', 'updated_at')


class CompanyProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating common company fields."""

    class Meta:
        model = CompanyProfile
        fields = (
            'company_name', 'company_email', 'company_registration_number',
            'country', 'address', 'phone_number', 'website',
            'industry', 'company_size', 'description'
        )


# --- 4. Job, Application, and Contract Serializers ---

class JobPostingSerializer(serializers.ModelSerializer):
    """Serializer for Job Posting creation and details."""
    company_name = serializers.ReadOnlyField(source='company.company_name')

    class Meta:
        model = JobPosting
        fields = '__all__'
        read_only_fields = ('id', 'company', 'created_at', 'updated_at')

    def validate(self, data):
        # Basic validation for salary range
        if data['salary_min'] >= data['salary_max']:
            raise serializers.ValidationError("Minimum salary must be less than maximum salary.")
        return data


class JobApplicationSerializer(serializers.ModelSerializer):
    """Serializer for Job Application creation and details."""
    freelancer_name = serializers.ReadOnlyField(source='freelancer.__str__')
    job_title = serializers.ReadOnlyField(source='job.title')

    class Meta:
        model = JobApplication
        fields = '__all__'
        read_only_fields = ('id', 'freelancer', 'job', 'status', 'applied_at', 'updated_at')

    def validate_freelancer(self, value):
        # Ensure the freelancer is verified before allowing application (business logic)
        if value.verification_status != 'verified':
            raise serializers.ValidationError("Only verified freelancers can apply for jobs.")
        return value


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract creation and details."""
    job_title = serializers.ReadOnlyField(source='job_application.job.title')
    freelancer_name = serializers.ReadOnlyField(source='freelancer.__str__')
    company_name = serializers.ReadOnlyField(source='company.company_name')

    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ('id', 'company', 'freelancer', 'status', 'created_at', 'updated_at')


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment details."""
    contract_details = ContractSerializer(source='contract', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('id', 'contract', 'platform_tax', 'dwelling_country_tax',
                            'work_country_tax', 'net_amount', 'status', 'payment_date',
                            'processed_at', 'transaction_reference')


# --- 5. Workspace and Task Serializers ---

class WorkspaceSerializer(serializers.ModelSerializer):
    """Serializer for Workspace details."""
    contract_id = serializers.ReadOnlyField(source='contract.id')

    class Meta:
        model = Workspace
        fields = '__all__'
        read_only_fields = ('id', 'contract', 'created_at', 'updated_at')


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task creation and details."""
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.__str__')
    created_by_email = serializers.ReadOnlyField(source='created_by.email')

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'created_by', 'created_at', 'updated_at')


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message creation and details."""
    sender_email = serializers.ReadOnlyField(source='sender.email')

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'sender', 'flagged', 'flag_reason', 'created_at')


# --- 6. Logging Serializer ---

class ProfileAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for Profile Access Log details."""
    company_name = serializers.ReadOnlyField(source='company.company_name')
    freelancer_name = serializers.ReadOnlyField(source='freelancer.__str__')

    class Meta:
        model = ProfileAccessLog
        fields = '__all__'
        read_only_fields = ('id', 'accessed_at', 'otp_verified')