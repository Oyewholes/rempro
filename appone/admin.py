from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, FreelancerProfile, CompanyProfile, OTPVerification,
    JobPosting, JobApplication, Contract, Payment, Workspace,
    Task, Message, ProfileAccessLog
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'user_type', 'is_verified', 'is_active', 'created_at']
    list_filter = ['user_type', 'is_verified', 'is_active', 'created_at']
    search_fields = ['email']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('user_type', 'is_verified')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'user_type', 'password1', 'password2'),
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'last_login']


@admin.register(FreelancerProfile)
class FreelancerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'get_full_name', 'user_email', 'phone_number', 'verification_status',
        'profile_completion', 'phone_verified', 'location_verified', 'created_at'
    ]
    list_filter = [
        'verification_status', 'phone_verified', 'location_verified',
        'bank_details_verified', 'country_code', 'created_at'
    ]
    search_fields = ['first_name', 'last_name', 'user__email', 'phone_number', 'nin']
    readonly_fields = [
        'digital_id', 'digital_id_link', 'profile_completion_percentage',
        'created_at', 'updated_at', 'admin_verified_at'
    ]

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'first_name', 'last_name', 'phone_number', 'phone_verified')
        }),
        ('Verification', {
            'fields': ('nin', 'verification_status', 'admin_verified_by', 'admin_verified_at')
        }),
        ('Location', {
            'fields': ('ip_address', 'country_code', 'location_verified')
        }),
        ('Documents', {
            'fields': ('cv_file', 'live_photo', 'portfolio_files')
        }),
        ('Digital Identity', {
            'fields': ('digital_id', 'digital_id_link', 'id_card_image')
        }),
        ('Banking', {
            'fields': ('paystack_email', 'payoneer_email', 'bank_details_verified')
        }),
        ('Profile Details', {
            'fields': ('skills', 'bio', 'approved_countries', 'profile_completion_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['verify_profiles', 'reject_profiles', 'generate_id_cards']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    get_full_name.short_description = 'Name'

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = 'Email'

    def profile_completion(self, obj):
        percentage = obj.profile_completion_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.0f}%</span>',
            color, percentage
        )

    profile_completion.short_description = 'Profile %'

    def verify_profiles(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(
            verification_status='verified',
            admin_verified_by=request.user,
            admin_verified_at=timezone.now()
        )
        self.message_user(request, f'{count} profile(s) verified successfully.')

    verify_profiles.short_description = 'Verify selected profiles'

    def reject_profiles(self, request, queryset):
        count = queryset.update(verification_status='rejected')
        self.message_user(request, f'{count} profile(s) rejected.')

    reject_profiles.short_description = 'Reject selected profiles'

    def generate_id_cards(self, request, queryset):
        from .tasks import generate_id_card_task
        count = 0
        for profile in queryset.filter(verification_status='verified'):
            generate_id_card_task.delay(profile.id)
            count += 1
        self.message_user(request, f'ID card generation initiated for {count} profile(s).')

    generate_id_cards.short_description = 'Generate ID cards'


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = [
        'company_name', 'company_email', 'country', 'verification_status',
        'api_verification_status', 'created_at'
    ]
    list_filter = ['verification_status', 'api_verification_status', 'country', 'industry', 'created_at']
    search_fields = ['company_name', 'company_email', 'company_registration_number']
    readonly_fields = ['verified_at', 'created_at', 'updated_at']

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Company Details', {
            'fields': (
                'company_name', 'company_email', 'company_registration_number',
                'country', 'address', 'phone_number', 'website'
            )
        }),
        ('Verification', {
            'fields': (
                'verification_status', 'meeting_scheduled_at', 'meeting_link',
                'api_verification_status', 'api_verification_data',
                'verified_by', 'verified_at'
            )
        }),
        ('Additional Info', {
            'fields': ('industry', 'company_size', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['verify_companies', 'reject_companies']

    def verify_companies(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(
            verification_status='verified',
            verified_by=request.user,
            verified_at=timezone.now()
        )
        self.message_user(request, f'{count} company(s) verified successfully.')

    verify_companies.short_description = 'Verify selected companies'

    def reject_companies(self, request, queryset):
        count = queryset.update(verification_status='rejected')
        self.message_user(request, f'{count} company(s) rejected.')

    reject_companies.short_description = 'Reject selected companies'


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'otp_type', 'otp_code', 'is_verified', 'expires_at', 'created_at']
    list_filter = ['otp_type', 'is_verified', 'created_at']
    search_fields = ['user__email', 'phone_number', 'email', 'otp_code']
    readonly_fields = ['created_at']


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'company_name', 'job_type', 'salary_range',
        'status', 'created_at', 'expires_at'
    ]
    list_filter = ['status', 'job_type', 'created_at']
    search_fields = ['title', 'description', 'company__company_name']
    readonly_fields = ['created_at', 'updated_at']

    def company_name(self, obj):
        return obj.company.company_name

    company_name.short_description = 'Company'

    def salary_range(self, obj):
        return f"{obj.currency} {obj.salary_min} - {obj.salary_max}"

    salary_range.short_description = 'Salary Range'


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'get_job_title', 'get_freelancer_name', 'get_company_name',
        'status', 'applied_at'
    ]
    list_filter = ['status', 'applied_at']
    search_fields = [
        'job__title', 'freelancer__first_name', 'freelancer__last_name',
        'job__company__company_name'
    ]
    readonly_fields = ['applied_at', 'updated_at']

    def get_job_title(self, obj):
        return obj.job.title

    get_job_title.short_description = 'Job'

    def get_freelancer_name(self, obj):
        return f"{obj.freelancer.first_name} {obj.freelancer.last_name}"

    get_freelancer_name.short_description = 'Freelancer'

    def get_company_name(self, obj):
        return obj.job.company.company_name

    get_company_name.short_description = 'Company'


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        'get_contract_name', 'get_freelancer', 'get_company',
        'monthly_rate', 'status', 'start_date', 'end_date'
    ]
    list_filter = ['status', 'start_date', 'created_at']
    search_fields = [
        'freelancer__first_name', 'freelancer__last_name',
        'company__company_name'
    ]
    readonly_fields = ['created_at', 'updated_at']

    def get_contract_name(self, obj):
        return f"Contract #{str(obj.id)[:8]}"

    get_contract_name.short_description = 'Contract'

    def get_freelancer(self, obj):
        return f"{obj.freelancer.first_name} {obj.freelancer.last_name}"

    get_freelancer.short_description = 'Freelancer'

    def get_company(self, obj):
        return obj.company.company_name

    get_company.short_description = 'Company'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_reference', 'get_contract', 'amount', 'net_amount',
        'status', 'payment_date', 'processed_at'
    ]
    list_filter = ['status', 'currency', 'payment_date']
    search_fields = ['transaction_reference', 'contract__id']
    readonly_fields = ['payment_date', 'processed_at']

    fieldsets = (
        ('Payment Details', {
            'fields': ('contract', 'amount', 'currency', 'status')
        }),
        ('Tax Breakdown', {
            'fields': (
                'platform_tax', 'dwelling_country_tax', 'work_country_tax', 'net_amount'
            )
        }),
        ('Transaction Info', {
            'fields': ('payment_method', 'transaction_reference', 'payment_date', 'processed_at')
        }),
    )

    def get_contract(self, obj):
        return f"Contract #{str(obj.contract.id)[:8]}"

    get_contract.short_description = 'Contract'


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_contract', 'created_at']
    search_fields = ['name', 'description', 'contract__id']
    readonly_fields = ['created_at', 'updated_at']

    def get_contract(self, obj):
        return f"Contract #{str(obj.contract.id)[:8]}"

    get_contract.short_description = 'Contract'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'get_workspace', 'get_assigned_to', 'status',
        'priority', 'due_date', 'created_at'
    ]
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['title', 'description', 'workspace__name']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']

    def get_workspace(self, obj):
        return obj.workspace.name

    get_workspace.short_description = 'Workspace'

    def get_assigned_to(self, obj):
        return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"

    get_assigned_to.short_description = 'Assigned To'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'get_sender', 'get_workspace', 'get_content_preview',
        'flagged', 'created_at'
    ]
    list_filter = ['flagged', 'created_at']
    search_fields = ['content', 'sender__email', 'workspace__name']
    readonly_fields = ['created_at']

    def get_sender(self, obj):
        return obj.sender.email

    get_sender.short_description = 'Sender'

    def get_workspace(self, obj):
        return obj.workspace.name

    get_workspace.short_description = 'Workspace'

    def get_content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content

    get_content_preview.short_description = 'Content'


@admin.register(ProfileAccessLog)
class ProfileAccessLogAdmin(admin.ModelAdmin):
    list_display = [
        'get_company', 'get_freelancer', 'otp_verified', 'accessed_at'
    ]
    list_filter = ['otp_verified', 'accessed_at']
    search_fields = ['company__company_name', 'freelancer__first_name', 'freelancer__last_name']
    readonly_fields = ['accessed_at']

    def get_company(self, obj):
        return obj.company.company_name

    get_company.short_description = 'Company'

    def get_freelancer(self, obj):
        return f"{obj.freelancer.first_name} {obj.freelancer.last_name}"

    get_freelancer.short_description = 'Freelancer'