import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal

from .models import (
    FreelancerProfile, CompanyProfile, JobPosting,
    JobApplication, Contract, Payment, OTPVerification
)

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def freelancer_user(db):
    user = User.objects.create_user(
        email='freelancer@test.com',
        password='testpass123',
        user_type='freelancer'
    )
    FreelancerProfile.objects.create(
        user=user,
        phone_number='+2348012345678',
        first_name='John',
        last_name='Doe',
        nin='12345678901'
    )
    return user


@pytest.fixture
def company_user(db):
    user = User.objects.create_user(
        email='company@test.com',
        password='testpass123',
        user_type='company'
    )
    CompanyProfile.objects.create(
        user=user,
        company_name='Test Corp',
        company_email='info@testcorp.com',
        company_registration_number='RC123456',
        country='USA',
        address='123 Test St',
        phone_number='+1234567890',
        industry='Technology',
        company_size='50-100'
    )
    return user


@pytest.fixture
def authenticated_freelancer(api_client, freelancer_user):
    api_client.force_authenticate(user=freelancer_user)
    return api_client


@pytest.fixture
def authenticated_company(api_client, company_user):
    api_client.force_authenticate(user=company_user)
    return api_client

@pytest.fixture
def admin_user(db):
    """Create an admin user (user_type='admin', is_staff=True)."""
    return User.objects.create_user(
        email='admin@test.com',
        password='adminpass123',
        user_type='admin',
        is_staff=True,
    )

@pytest.fixture
def authenticated_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def company_with_proposed_dates(company_user):
    """Company profile with 3 proposed meeting dates set 48h+ in the future."""
    profile = company_user.company_profile
    base = timezone.now() + timedelta(days=3)
    profile.proposed_meeting_dates = [
        (base).isoformat(),
        (base + timedelta(days=1)).isoformat(),
        (base + timedelta(days=2)).isoformat(),
    ]
    profile.verification_status = 'scheduled'
    profile.save()
    return profile


# Authentication Tests
@pytest.mark.django_db
class TestAuthentication:

    def test_user_registration_freelancer(self, api_client):
        url = reverse('auth-register')
        data = {
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123',
            'user_type': 'freelancer'
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'tokens' in response.data
        assert User.objects.filter(email='newuser@test.com').exists()

    def test_user_registration_password_mismatch(self, api_client):
        url = reverse('auth-register')
        data = {
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'confirm_password': 'differentpass',
            'user_type': 'freelancer'
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_login_success(self, api_client, freelancer_user):
        url = reverse('auth-login')
        data = {
            'email': 'freelancer@test.com',
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']

    def test_user_login_invalid_credentials(self, api_client, freelancer_user):
        url = reverse('auth-login')
        data = {
            'email': 'freelancer@test.com',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# OTP Tests
@pytest.mark.django_db
class TestOTP:

    def test_send_phone_otp(self, authenticated_freelancer):
        url = reverse('otp-send-phone-otp')
        data = {'phone_number': '+2348012345678'}
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert OTPVerification.objects.filter(
            otp_type='phone',
            phone_number='+2348012345678'
        ).exists()

    def test_send_phone_otp_invalid_format(self, authenticated_freelancer):
        url = reverse('otp-send-phone-otp')
        data = {'phone_number': '1234567890'}  # Invalid format
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_phone_otp_success(self, authenticated_freelancer, freelancer_user):
        # Create OTP
        otp = OTPVerification.objects.create(
            user=freelancer_user,
            otp_code='123456',
            otp_type='phone',
            phone_number='+2348012345678',
            expires_at=datetime.now() + timedelta(minutes=10)
        )

        url = reverse('otp-verify-phone-otp')
        data = {'otp_code': '123456'}
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        # Check profile updated
        profile = freelancer_user.freelancer_profile
        profile.refresh_from_db()
        assert profile.phone_verified is True


# Freelancer Profile Tests
@pytest.mark.django_db
class TestFreelancerProfile:

    def test_get_profile(self, authenticated_freelancer, freelancer_user):
        url = reverse('freelancer-me')
        response = authenticated_freelancer.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'John'
        assert response.data['last_name'] == 'Doe'

    def test_update_profile(self, authenticated_freelancer, freelancer_user):
        url = reverse('freelancer-me')
        data = {
            'first_name': 'Jane',
            'skills': ['Python', 'Django'],
            'bio': 'Experienced developer'
        }
        response = authenticated_freelancer.patch(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        profile = freelancer_user.freelancer_profile
        profile.refresh_from_db()
        assert profile.first_name == 'Jane'
        assert 'Python' in profile.skills

    def test_upload_cv(self, authenticated_freelancer):
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse('freelancer-upload-cv')
        cv_file = SimpleUploadedFile("cv.pdf", b"file_content", content_type="application/pdf")
        response = authenticated_freelancer.post(url, {'cv_file': cv_file}, format='multipart')

        assert response.status_code == status.HTTP_200_OK
        assert 'cv_url' in response.data

    def test_add_nin(self, authenticated_freelancer, freelancer_user):
        url = reverse('freelancer-add-nin')
        data = {'nin': '12345678901'}
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        profile = freelancer_user.freelancer_profile
        profile.refresh_from_db()
        assert profile.nin == '12345678901'

    def test_profile_completion_calculation(self, freelancer_user):
        profile = freelancer_user.freelancer_profile
        initial_completion = profile.profile_completion_percentage

        # Add more info
        profile.phone_verified = True
        profile.cv_file = 'cvs/test.pdf'
        profile.live_photo = 'photos/test.jpg'
        profile.location_verified = True
        profile.paystack_email = 'test@example.com'
        profile.save()

        profile.calculate_profile_completion()

        assert profile.profile_completion_percentage > initial_completion


# Company Profile Tests
@pytest.mark.django_db
class TestCompanyProfile:

    def test_get_company_profile(self, authenticated_company, company_user):
        url = reverse('company-me')
        response = authenticated_company.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['company_name'] == 'Test Corp'

    def test_schedule_meeting(self, authenticated_company, company_user):
        url = reverse('company-schedule-verification-meeting')
        data = {
            'meeting_date': '2024-02-01T10:00:00Z',
            'meeting_link': 'https://meet.google.com/test'
        }
        response = authenticated_company.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        profile = company_user.company_profile
        profile.refresh_from_db()
        assert profile.verification_status == 'scheduled'


# Job Posting Tests
@pytest.mark.django_db
class TestJobPosting:

    def test_create_job_posting(self, authenticated_company, company_user):
        url = reverse('jobs-list')
        data = {
            'title': 'Software Engineer',
            'description': 'We are looking for...',
            'required_skills': ['Python', 'Django'],
            'required_countries': ['USA'],
            'job_type': 'Full-time',
            'salary_min': 5000,
            'salary_max': 8000,
            'currency': 'USD',
            'status': 'draft'
        }
        response = authenticated_company.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert JobPosting.objects.filter(title='Software Engineer').exists()

    def test_list_jobs_as_freelancer(self, authenticated_freelancer, company_user):
        # Create a job
        JobPosting.objects.create(
            company=company_user.company_profile,
            title='Developer',
            description='Test job',
            required_skills=['Python'],
            required_countries=['USA'],
            job_type='Full-time',
            salary_min=5000,
            salary_max=8000,
            status='active'
        )

        url = reverse('jobs-list')
        response = authenticated_freelancer.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0


# Job Application Tests
@pytest.mark.django_db
class TestJobApplication:

    def test_apply_for_job(self, authenticated_freelancer, freelancer_user, company_user):
        # Verify freelancer first
        profile = freelancer_user.freelancer_profile
        profile.verification_status = 'verified'
        profile.save()

        # Create job
        job = JobPosting.objects.create(
            company=company_user.company_profile,
            title='Developer',
            description='Test job',
            required_skills=['Python'],
            required_countries=['USA'],
            job_type='Full-time',
            salary_min=5000,
            salary_max=8000,
            status='active'
        )

        url = reverse('applications-list')
        data = {
            'job': str(job.id),
            'cover_letter': 'I am interested in this position...'
        }
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert JobApplication.objects.filter(job=job, freelancer=profile).exists()

    def test_cannot_apply_without_verification(self, authenticated_freelancer, freelancer_user, company_user):
        # Create job
        job = JobPosting.objects.create(
            company=company_user.company_profile,
            title='Developer',
            description='Test job',
            required_skills=['Python'],
            required_countries=['USA'],
            job_type='Full-time',
            salary_min=5000,
            salary_max=8000,
            status='active'
        )

        url = reverse('applications-list')
        data = {
            'job': str(job.id),
            'cover_letter': 'I am interested...'
        }
        response = authenticated_freelancer.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# Payment Tests
@pytest.mark.django_db
class TestPayment:

    def test_calculate_payment_taxes(self):
        from .utils import calculate_payment_breakdown

        # Create mock contract
        class MockContract:
            platform_tax_rate = Decimal('5.00')
            dwelling_country_tax_rate = Decimal('5.00')
            work_country_tax_rate = Decimal('5.00')

        contract = MockContract()
        breakdown = calculate_payment_breakdown(Decimal('2000.00'), contract)

        assert breakdown['gross_amount'] == 2000.0
        assert breakdown['platform_tax'] == 100.0
        assert breakdown['dwelling_country_tax'] == 100.0
        assert breakdown['work_country_tax'] == 100.0
        assert breakdown['net_amount'] == 1700.0


# Message Flagging Tests
@pytest.mark.django_db
class TestMessageFlagging:

    def test_flag_suspicious_message(self):
        from .utils import flag_suspicious_message

        # Test email detection
        is_flagged, reason = flag_suspicious_message("Contact me at test@example.com")
        assert is_flagged is True

        # Test phone detection
        is_flagged, reason = flag_suspicious_message("Call me at +2348012345678")
        assert is_flagged is True

        # Test normal message
        is_flagged, reason = flag_suspicious_message("Let's discuss the project requirements")
        assert is_flagged is False

@pytest.mark.django_db
class TestAdminEndpoints:
    # ── company_proposed_dates ────────────────────────────────────────────
    def test_list_proposed_dates(self, authenticated_admin, company_with_proposed_dates):
        url = reverse('admin-company-proposed-dates')
        response = authenticated_admin.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert len(response.data['results'][0]['proposed_meeting_dates']) == 3

    def test_list_proposed_dates_non_admin_forbidden(self, authenticated_freelancer):
        url = reverse('admin-company-proposed-dates')
        response = authenticated_freelancer.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ── confirm_meeting ──────────────────────────────────────────────────
    def test_confirm_meeting_success(
        self, authenticated_admin, company_with_proposed_dates
    ):
        profile = company_with_proposed_dates
        selected = profile.proposed_meeting_dates[0]  # 3 days from now
        url = reverse('admin-confirm-meeting')
        data = {
            'company_id': profile.id,
            'selected_date': selected,
            'meeting_link': 'https://meet.google.com/abc-defg-hij',
        }
        response = authenticated_admin.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['company_id'] == profile.id
        profile.refresh_from_db()
        assert profile.verification_status == 'scheduled'
        assert profile.meeting_link == 'https://meet.google.com/abc-defg-hij'
        assert profile.meeting_scheduled_at is not None

    def test_confirm_meeting_not_in_proposed(
        self, authenticated_admin, company_with_proposed_dates
    ):
        profile = company_with_proposed_dates
        wrong_date = (timezone.now() + timedelta(days=10)).isoformat()
        url = reverse('admin-confirm-meeting')
        data = {
            'company_id': profile.id,
            'selected_date': wrong_date,
            'meeting_link': 'https://meet.google.com/abc-defg-hij',
        }
        response = authenticated_admin.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_meeting_too_soon(
        self, authenticated_admin, company_user
    ):
        """Date less than 24h in the future should be rejected."""
        profile = company_user.company_profile
        too_soon = (timezone.now() + timedelta(hours=2)).isoformat()
        profile.proposed_meeting_dates = [too_soon]
        profile.verification_status = 'scheduled'
        profile.save()
        url = reverse('admin-confirm-meeting')
        data = {
            'company_id': profile.id,
            'selected_date': too_soon,
            'meeting_link': 'https://meet.google.com/abc-defg-hij',
        }
        response = authenticated_admin.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── verify_company ───────────────────────────────────────────────────
    def test_verify_company_success(
        self, authenticated_admin, company_user
    ):
        profile = company_user.company_profile
        url = reverse('admin-verify-company')
        data = {
            'company_id': profile.id,
            'verification_status': 'verified',
        }
        response = authenticated_admin.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.verification_status == 'verified'
        assert profile.verified_at is not None
        assert profile.verified_by is not None
        company_user.refresh_from_db()
        assert company_user.is_verified is True

    def test_verify_company_reject(
        self, authenticated_admin, company_user
    ):
        profile = company_user.company_profile
        url = reverse('admin-verify-company')
        data = {
            'company_id': profile.id,
            'verification_status': 'rejected',
            'notes': 'Documents do not match.',
        }
        response = authenticated_admin.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.verification_status == 'rejected'

    def test_verify_company_non_admin_forbidden(
        self, authenticated_freelancer, company_user
    ):
        profile = company_user.company_profile
        url = reverse('admin-verify-company')
        data = {
            'company_id': profile.id,
            'verification_status': 'verified',
        }
        response = authenticated_freelancer.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
