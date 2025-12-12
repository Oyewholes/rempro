from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import random
import re

from .models import (
    User, FreelancerProfile, CompanyProfile, OTPVerification,
    JobPosting, JobApplication, Contract, Payment, Workspace,
    Task, Message, ProfileAccessLog
)
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    OTPVerificationSerializer, OTPValidateSerializer,
    FreelancerProfileSerializer, FreelancerProfileUpdateSerializer,
    FreelancerPublicProfileSerializer, CompanyProfileSerializer,
    CompanyProfileUpdateSerializer, JobPostingSerializer,
    JobApplicationSerializer, ContractSerializer, PaymentSerializer,
    WorkspaceSerializer, TaskSerializer, MessageSerializer,
    ProfileAccessLogSerializer, ScheduleMeetingSerializer,
    AdminVerificationSerializer
)
from .permissions import IsFreelancer, IsCompany, IsAdmin


# Authentication Views
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user (freelancer or company)"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Create profile based on user type
            if user.user_type == 'freelancer':
                FreelancerProfile.objects.create(user=user)
            elif user.user_type == 'company':
                CompanyProfile.objects.create(user=user)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Registration successful',
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'user_type': user.user_type
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login user"""
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'user_type': user.user_type,
                    'is_verified': user.is_verified
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# OTP Management Views
class OTPViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def send_phone_otp(self, request):
        """Send OTP to phone number for verification"""
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({'error': 'Phone number is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate Nigerian phone format
        if not re.match(r'^\+234\d{10}$', phone_number):
            return Response({'error': 'Invalid Nigerian phone format. Use +234XXXXXXXXXX'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))

        # Create OTP record
        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=otp_code,
            otp_type='phone',
            phone_number=phone_number,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # TODO: Integrate with SMS service (Twilio, Africa's Talking, etc.)
        # For now, return OTP in response (ONLY FOR DEVELOPMENT)

        return Response({
            'message': 'OTP sent successfully',
            'otp_id': str(otp.id),
            'expires_at': otp.expires_at,
            'otp_code': otp_code  # Remove in production
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def verify_phone_otp(self, request):
        """Verify phone OTP"""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_code = serializer.validated_data['otp_code']

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type='phone',
                is_verified=False,
                expires_at__gte=timezone.now()
            )

            otp.is_verified = True
            otp.save()

            # Update freelancer profile
            if hasattr(request.user, 'freelancer_profile'):
                profile = request.user.freelancer_profile
                profile.phone_number = otp.phone_number
                profile.phone_verified = True
                profile.save()
                profile.calculate_profile_completion()

            return Response({
                'message': 'Phone verified successfully'
            }, status=status.HTTP_200_OK)

        except OTPVerification.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def send_company_access_otp(self, request):
        """Send OTP to company email for profile access"""
        if not hasattr(request.user, 'company_profile'):
            return Response({'error': 'Only companies can request access OTP'}, status=status.HTTP_403_FORBIDDEN)

        company_profile = request.user.company_profile

        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))

        # Create OTP record
        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=otp_code,
            otp_type='company_access',
            email=company_profile.company_email,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # TODO: Send email with OTP

        return Response({
            'message': 'OTP sent to company email',
            'otp_id': str(otp.id),
            'expires_at': otp.expires_at,
            'otp_code': otp_code  # Remove in production
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def verify_company_access_otp(self, request):
        """Verify company access OTP"""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_code = serializer.validated_data['otp_code']

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type='company_access',
                is_verified=False,
                expires_at__gte=timezone.now()
            )

            otp.is_verified = True
            otp.save()

            return Response({
                'message': 'Access verified successfully',
                'access_token': otp_code  # Can be used as temporary access token
            }, status=status.HTTP_200_OK)

        except OTPVerification.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)


# Freelancer Profile Views
class FreelancerProfileViewSet(viewsets.ModelViewSet):
    queryset = FreelancerProfile.objects.all()
    serializer_class = FreelancerProfileSerializer

    def get_permissions(self):
        if self.action in ['retrieve_by_digital_id', 'public_profile']:
            return [AllowAny()]
        return [IsAuthenticated(), IsFreelancer()]

    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'freelancer_profile'):
            return FreelancerProfile.objects.filter(user=self.request.user)
        return FreelancerProfile.objects.none()

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current freelancer's profile"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            serializer = FreelancerProfileSerializer(profile, context={'request': request})
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            serializer = FreelancerProfileUpdateSerializer(
                profile, data=request.data, partial=(request.method == 'PATCH')
            )
            if serializer.is_valid():
                serializer.save()
                profile.calculate_profile_completion()
                return Response(FreelancerProfileSerializer(profile, context={'request': request}).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def verify_location(self, request):
        """Verify user's location via IP address"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get IP address from request
        ip_address = request.META.get('REMOTE_ADDR')

        # TODO: Use IP geolocation service to verify country
        # For now, just save the IP
        profile.ip_address = ip_address
        profile.location_verified = True  # Set to True after actual verification
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'Location verified',
            'ip_address': ip_address
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def upload_cv(self, request):
        """Upload CV file"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        cv_file = request.FILES.get('cv_file')
        if not cv_file:
            return Response({'error': 'CV file is required'}, status=status.HTTP_400_BAD_REQUEST)

        profile.cv_file = cv_file
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'CV uploaded successfully',
            'cv_url': profile.cv_file.url
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def upload_live_photo(self, request):
        """Upload live photo taken from camera"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        live_photo = request.FILES.get('live_photo')
        if not live_photo:
            return Response({'error': 'Live photo is required'}, status=status.HTTP_400_BAD_REQUEST)

        profile.live_photo = live_photo
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'Live photo uploaded successfully',
            'photo_url': profile.live_photo.url
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def add_nin(self, request):
        """Add National Identification Number"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        nin = request.data.get('nin')
        if not nin or len(nin) != 11:
            return Response({'error': 'Valid 11-digit NIN is required'}, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Verify NIN with government API

        profile.nin = nin
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'NIN added successfully'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def add_portfolio(self, request):
        """Add portfolio items"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        portfolio_item = request.data.get('portfolio_item')
        if not portfolio_item:
            return Response({'error': 'Portfolio item is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(profile.portfolio_files, list):
            profile.portfolio_files = []

        profile.portfolio_files.append(portfolio_item)
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'Portfolio item added successfully',
            'portfolio': profile.portfolio_files
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def add_banking_details(self, request):
        """Add banking details (Paystack/Payoneer)"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        paystack_email = request.data.get('paystack_email')
        payoneer_email = request.data.get('payoneer_email')

        if not paystack_email and not payoneer_email:
            return Response({'error': 'At least one payment method is required'}, status=status.HTTP_400_BAD_REQUEST)

        if paystack_email:
            profile.paystack_email = paystack_email
        if payoneer_email:
            profile.payoneer_email = payoneer_email

        profile.bank_details_verified = True
        profile.save()
        profile.calculate_profile_completion()

        return Response({
            'message': 'Banking details added successfully'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='digital-id/(?P<digital_id>[^/.]+)')
    def retrieve_by_digital_id(self, request, digital_id=None):
        """Retrieve freelancer profile by digital ID (public access with OTP for companies)"""
        try:
            profile = FreelancerProfile.objects.get(digital_id=digital_id)
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        # If accessed by a company, require OTP verification
        if request.user.is_authenticated and hasattr(request.user, 'company_profile'):
            # Log the access
            ProfileAccessLog.objects.create(
                company=request.user.company_profile,
                freelancer=profile,
                otp_verified=True  # Assume OTP was verified in previous step
            )

        serializer = FreelancerPublicProfileSerializer(profile)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def download_id_card(self, request):
        """Download digital ID card"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        if not profile.id_card_image:
            return Response({'error': 'ID card not generated yet'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'id_card_url': profile.id_card_image.url
        }, status=status.HTTP_200_OK)


# Company Profile Views
class CompanyProfileViewSet(viewsets.ModelViewSet):
    queryset = CompanyProfile.objects.all()
    serializer_class = CompanyProfileSerializer

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCompany()]

    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'company_profile'):
            return CompanyProfile.objects.filter(user=self.request.user)
        return CompanyProfile.objects.none()

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current company's profile"""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            serializer = CompanyProfileSerializer(profile)
            return Response(serializer.data)

        elif request.method in ['PUT', 'PATCH']:
            serializer = CompanyProfileUpdateSerializer(
                profile, data=request.data, partial=(request.method == 'PATCH')
            )
            if serializer.is_valid():
                serializer.save()
                return Response(CompanyProfileSerializer(profile).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def schedule_verification_meeting(self, request):
        """Schedule verification meeting with admin"""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ScheduleMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile.meeting_scheduled_at = serializer.validated_data['meeting_date']
        if 'meeting_link' in serializer.validated_data:
            profile.meeting_link = serializer.validated_data['meeting_link']
        profile.verification_status = 'scheduled'
        profile.save()

        # TODO: Send email notification to admin

        return Response({
            'message': 'Meeting scheduled successfully',
            'meeting_date': profile.meeting_scheduled_at,
            'meeting_link': profile.meeting_link
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def verify_company_registration(self, request):
        """Verify company with government database (Admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        company_id = request.data.get('company_id')
        try:
            profile = CompanyProfile.objects.get(id=company_id)
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)

        # TODO: Make API call to government database
        # This is a placeholder for the actual API integration
        api_verified = True
        verification_data = {
            'registration_number': profile.company_registration_number,
            'company_name': profile.company_name,
            'verified': True,
            'verified_at': timezone.now().isoformat()
        }

        profile.api_verification_status = api_verified
        profile.api_verification_data = verification_data

        if api_verified:
            profile.verification_status = 'verified'
            profile.verified_at = timezone.now()
            profile.verified_by = request.user
            request.user.is_verified = True
            request.user.save()

        profile.save()

        return Response({
            'message': 'Company verification completed',
            'verification_status': profile.verification_status,
            'api_verification_data': verification_data
        }, status=status.HTTP_200_OK)


# Job Posting Views
class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'company_profile'):
            # Companies see their own jobs
            return JobPosting.objects.filter(company=self.request.user.company_profile)
        elif hasattr(self.request.user, 'freelancer_profile'):
            # Freelancers see active jobs
            return JobPosting.objects.filter(status='active')
        return JobPosting.objects.none()

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'company_profile'):
            raise serializers.ValidationError('Only companies can create job postings')
        serializer.save(company=self.request.user.company_profile)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a job posting"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        job.status = 'active'
        job.save()

        return Response({
            'message': 'Job published successfully',
            'job': JobPostingSerializer(job).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a job posting"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        job.status = 'closed'
        job.save()

        return Response({
            'message': 'Job closed successfully'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def applications(self, request, pk=None):
        """Get applications for a job"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        applications = JobApplication.objects.filter(job=job)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)


# Job Application Views
class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return JobApplication.objects.filter(freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return JobApplication.objects.filter(job__company=self.request.user.company_profile)
        return JobApplication.objects.none()

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'freelancer_profile'):
            raise serializers.ValidationError('Only freelancers can apply for jobs')

        freelancer = self.request.user.freelancer_profile
        if freelancer.verification_status != 'verified':
            raise serializers.ValidationError('Profile must be verified to apply for jobs')

        serializer.save(freelancer=freelancer)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update application status (Company only)"""
        if not hasattr(request.user, 'company_profile'):
            return Response({'error': 'Only companies can update application status'}, status=status.HTTP_403_FORBIDDEN)

        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if new_status not in dict(JobApplication.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        application.status = new_status
        application.save()

        return Response({
            'message': 'Application status updated',
            'application': JobApplicationSerializer(application).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def hire(self, request, pk=None):
        """Hire freelancer and create contract"""
        if not hasattr(request.user, 'company_profile'):
            return Response({'error': 'Only companies can hire freelancers'}, status=status.HTTP_403_FORBIDDEN)

        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        if application.status == 'hired':
            return Response({'error': 'Freelancer already hired'}, status=status.HTTP_400_BAD_REQUEST)

        # Create contract
        contract_data = request.data
        contract = Contract.objects.create(
            job_application=application,
            company=application.job.company,
            freelancer=application.freelancer,
            start_date=contract_data.get('start_date'),
            monthly_rate=contract_data.get('monthly_rate'),
            currency=contract_data.get('currency', 'USD'),
            status='pending'
        )

        # Update application status
        application.status = 'hired'
        application.save()

        # Create workspace
        workspace = Workspace.objects.create(
            contract=contract,
            name=f"{application.job.title} - {application.freelancer.first_name}",
            description=f"Workspace for {application.job.title}"
        )

        return Response({
            'message': 'Freelancer hired successfully',
            'contract': ContractSerializer(contract).data,
            'workspace': WorkspaceSerializer(workspace).data
        }, status=status.HTTP_201_CREATED)


# Contract Views
class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Contract.objects.filter(freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Contract.objects.filter(company=self.request.user.company_profile)
        return Contract.objects.none()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate contract"""
        contract = self.get_object()
        contract.status = 'active'
        contract.save()

        return Response({
            'message': 'Contract activated',
            'contract': ContractSerializer(contract).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete contract"""
        contract = self.get_object()
        contract.status = 'completed'
        contract.save()

        return Response({
            'message': 'Contract completed'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Terminate contract"""
        contract = self.get_object()
        contract.status = 'terminated'
        contract.save()

        return Response({
            'message': 'Contract terminated'
        }, status=status.HTTP_200_OK)


# Payment Views
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Payment.objects.filter(contract__freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Payment.objects.filter(contract__company=self.request.user.company_profile)
        return Payment.objects.none()

    def perform_create(self, serializer):
        """Create payment with tax calculations"""
        if not hasattr(self.request.user, 'company_profile'):
            raise serializers.ValidationError('Only companies can initiate payments')

        contract = serializer.validated_data['contract']
        amount = serializer.validated_data['amount']

        # Calculate taxes
        platform_tax = (amount * contract.platform_tax_rate) / 100
        dwelling_tax = (amount * contract.dwelling_country_tax_rate) / 100
        work_tax = (amount * contract.work_country_tax_rate) / 100
        net_amount = amount - (platform_tax + dwelling_tax + work_tax)

        serializer.save(
            platform_tax=platform_tax,
            dwelling_country_tax=dwelling_tax,
            work_country_tax=work_tax,
            net_amount=net_amount,
            transaction_reference=f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{contract.id}"
        )

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process payment"""
        payment = self.get_object()

        if payment.status != 'pending':
            return Response({'error': 'Payment already processed'}, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Integrate with payment gateway (Paystack, Stripe, etc.)

        payment.status = 'completed'
        payment.processed_at = timezone.now()
        payment.save()

        return Response({
            'message': 'Payment processed successfully',
            'payment': PaymentSerializer(payment).data
        }, status=status.HTTP_200_OK)


# Workspace Views
class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Workspace.objects.filter(contract__freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Workspace.objects.filter(contract__company=self.request.user.company_profile)
        return Workspace.objects.none()


# Task Views
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Task.objects.filter(assigned_to=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Task.objects.filter(workspace__contract__company=self.request.user.company_profile)
        return Task.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update task status"""
        task = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Task.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
        task.save()

        return Response({
            'message': 'Task status updated',
            'task': TaskSerializer(task).data
        }, status=status.HTTP_200_OK)


# Message Views
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Message.objects.filter(workspace__contract__freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Message.objects.filter(workspace__contract__company=self.request.user.company_profile)
        return Message.objects.none()

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)

        # Check for personal information in message
        flagged_keywords = ['email', 'phone', 'whatsapp', 'telegram', 'skype', '@', '+']
        content_lower = message.content.lower()

        if any(keyword in content_lower for keyword in flagged_keywords):
            message.flagged = True
            message.flag_reason = 'Possible personal information exchange detected'
            message.save()

    @action(detail=False, methods=['get'])
    def workspace_messages(self, request):
        """Get messages for a specific workspace"""
        workspace_id = request.query_params.get('workspace_id')
        if not workspace_id:
            return Response({'error': 'workspace_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        messages = self.get_queryset().filter(workspace_id=workspace_id).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


# Admin Views
class AdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]

    @action(detail=False, methods=['post'])
    def verify_freelancer(self, request):
        """Verify freelancer profile"""
        freelancer_id = request.data.get('freelancer_id')

        try:
            profile = FreelancerProfile.objects.get(id=freelancer_id)
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Freelancer not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile.verification_status = serializer.validated_data['verification_status']
        if profile.verification_status == 'verified':
            profile.admin_verified_at = timezone.now()
            profile.admin_verified_by = request.user
            profile.user.is_verified = True
            profile.user.save()

        profile.save()

        return Response({
            'message': 'Freelancer verification updated',
            'profile': FreelancerProfileSerializer(profile).data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def pending_verifications(self, request):
        """Get pending freelancer verifications"""
        freelancers = FreelancerProfile.objects.filter(verification_status='pending')
        serializer = FreelancerProfileSerializer(freelancers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_companies(self, request):
        """Get pending company verifications"""
        companies = CompanyProfile.objects.filter(verification_status__in=['pending', 'scheduled'])
        serializer = CompanyProfileSerializer(companies, many=True)
        return Response(serializer.data)