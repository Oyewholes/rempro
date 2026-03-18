from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
import uuid
from decimal import Decimal

phone_validator = RegexValidator(regex=r'^\+234\d{10}$', message="Phone must be in format: '+234XXXXXXXXXX'")

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('freelancer', 'Freelancer'),
        ('company', 'Company'),
        ('admin', 'Admin'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(validators=[phone_validator], max_length=14, unique=False, blank=True)
    phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_type']

    def __str__(self):
        return self.email


class FreelancerProfile(models.Model):
    VERIFICATION_STATUS = (
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='freelancer_profile')
    phone_number = models.CharField(validators=[phone_validator], max_length=14, unique=False, blank=True)
    phone_verified = models.BooleanField(default=False)

    # Personal Information
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    nin = models.CharField(max_length=11, unique=True, help_text="National Identification Number", blank=True)

    # Location Verification
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country_code = models.CharField(max_length=3, default='NGA')
    location_verified = models.BooleanField(default=False)

    # Documents
    cv_file = models.URLField(null=True, blank=True)
    live_photo = models.URLField(null=True, blank=True)
    portfolio_files = models.JSONField(default=list, blank=True)

    # Digital Identity
    digital_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    digital_id_link = models.CharField(max_length=500, blank=True)
    id_card_image = models.URLField(null=True, blank=True)

    # Verification
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    admin_verified_at = models.DateTimeField(null=True, blank=True)
    admin_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                          related_name='verified_freelancers')

    # Profile Completion
    profile_completion_percentage = models.IntegerField(default=0)

    # Banking Details
    paystack_email = models.EmailField(null=True, blank=True)
    payoneer_email = models.EmailField(null=True, blank=True)
    bank_details_verified = models.BooleanField(default=False)

    # Skills and Experience
    skills = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)

    # Approved Countries for Work
    approved_countries = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def calculate_profile_completion(self):
        fields = [
            self.phone_verified,
            bool(self.cv_file),
            bool(self.live_photo),
            bool(self.nin),
            self.location_verified,
            bool(self.paystack_email or self.payoneer_email),
            bool(self.portfolio_files),
            bool(self.skills),
            bool(self.bio),
        ]
        completed = sum(fields)
        self.profile_completion_percentage = int((completed / len(fields)) * 100)
        self.save(update_fields=['profile_completion_percentage'])
        return self.profile_completion_percentage


class CompanyProfile(models.Model):
    VERIFICATION_STATUS = (
        ('pending', 'Pending'),
        ('scheduled', 'Meeting Scheduled'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')

    # Company Information
    company_name = models.CharField(max_length=255, blank=True)
    company_email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    company_registration_number = models.CharField(max_length=100, unique=False, blank=True)
    country = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(validators=[phone_validator], max_length=14, unique=True, blank=True)
    website = models.URLField(blank=True)

    # Verification
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    meeting_scheduled_at = models.DateTimeField(null=True, blank=True)
    meeting_link = models.URLField(blank=True)
    api_verification_status = models.BooleanField(default=False)
    api_verification_data = models.JSONField(default=dict, blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='verified_companies')

    # Company Details
    industry = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name


class OTPVerification(models.Model):
    OTP_TYPE_CHOICES = (
        ('phone', 'Phone Verification'),
        ('company_email', 'Company Email'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES)
    phone_number = models.CharField(validators=[phone_validator], max_length=14, unique=False)
    email = models.EmailField(blank=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.email} - {self.otp_type}"


class JobPosting(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name='job_postings')

    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.JSONField(default=list)
    required_countries = models.JSONField(default=list, help_text="Countries where virtual work permit is required")

    job_type = models.CharField(max_length=50)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.company.company_name}"


class JobApplication(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    freelancer = models.ForeignKey(FreelancerProfile, on_delete=models.CASCADE, related_name='applications')

    cover_letter = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'freelancer')

    def __str__(self):
        return f"{self.freelancer} - {self.job.title}"


class Contract(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name='contract')
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name='contracts')
    freelancer = models.ForeignKey(FreelancerProfile, on_delete=models.CASCADE, related_name='contracts')

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Tax Information
    platform_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    dwelling_country_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    work_country_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Contract: {self.freelancer} - {self.company.company_name}"


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='payments')

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    # Tax Breakdown
    platform_tax = models.DecimalField(max_digits=10, decimal_places=2)
    dwelling_country_tax = models.DecimalField(max_digits=10, decimal_places=2)
    work_country_tax = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    payment_date = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    payment_method = models.CharField(max_length=50)
    transaction_reference = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"Payment: {self.contract} - {self.amount} {self.currency}"


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, related_name='workspace')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Workspace: {self.name}"


class Task(models.Model):
    STATUS_CHOICES = (
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='tasks')

    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, default='medium')

    assigned_to = models.ForeignKey(FreelancerProfile, on_delete=models.CASCADE, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')

    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.workspace.name}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')

    content = models.TextField()
    flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.email} in {self.workspace.name}"


class ProfileAccessLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name='access_logs')
    freelancer = models.ForeignKey(FreelancerProfile, on_delete=models.CASCADE, related_name='profile_access_logs')

    accessed_at = models.DateTimeField(auto_now_add=True)
    otp_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company.company_name} accessed {self.freelancer}"