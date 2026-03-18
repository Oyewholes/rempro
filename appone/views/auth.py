from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from appone.serializer import RegisterCompanySerializer, RegisterFreelancerSerializer, LoginSerializer
from appone.tasks import send_otp_task, send_company_email_otp_task
from appone.models import OTPVerification
from django.utils import timezone
from datetime import timedelta
from RemPro import settings
from appone.utils import generate_otp


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register_freelancer(self, request):
        """
                Register a new freelancer user.

                Required body:
                    email, password, password2, user_type, phone_number

                On success:
                    - Creates User
                    - Creates FreelancerProfile (seeded with phone_number)
                    - Creates a pending OTPVerification record (phone type)
                    - Sends the OTP code in the background
                """
        serializer = RegisterFreelancerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Registration successful. An OTP has been sent to your phone number.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'user_type': user.user_type,
                'phone_number': user.phone_number,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def resend_freelancer_otp(self, request):
        """
        Resend phone OTP to an already-registered freelancer.
        Invalidates any existing unexpired OTP and creates a fresh one.
        """
        if not hasattr(request.user, 'freelancer_profile'):
            return Response(
                {'error': 'Only freelancer accounts can use this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )
        if request.user.phone_verified:
            return Response(
                {'error': 'Your phone number is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Expire any existing unverified phone OTPs for this user
        OTPVerification.objects.filter(
            user=request.user,
            otp_type='phone',
            is_verified=False,
        ).update(expires_at=timezone.now())

        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=generate_otp(),
            otp_type='phone',
            phone_number=request.user.phone_number,
            email=request.user.email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        try:
            send_otp_task.delay(otp.id)
        except Exception:
            send_otp_task(otp.id)

        response_data = {
            'message': 'A new OTP has been sent to your phone number.',
            'otp_id': str(otp.id),
            'expires_at': otp.expires_at,
        }
        if settings.DEBUG:
            response_data['otp_code'] = otp.otp_code

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login user"""
        serializer = LoginSerializer(data=request.data)
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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """Logout user by blacklisting their refresh token."""
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token= RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'message': 'Logged out successfully.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except TokenError as e:
            return Response(
                {'error': f'Invalid or already revoked token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def register_company(self, request):
        """
                Register a new Company user.

                Required body:
                    email, password, password2, user_type

                On success:
                    - Creates User
                    - Creates CompanyProfile
                    - Creates a pending OTPVerification record (Company Email type)
                    - Sends the OTP code in the background
                """
        serializer = RegisterCompanySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Registration successful. An OTP has been sent to your email.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'user_type': user.user_type,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def resend_company_otp(self, request):
        """
                Resend phone OTP to an already-registered company.
                Invalidates any existing unexpired OTP and creates a fresh one.
                """
        if not hasattr(request.user, 'company_profile'):
            return Response(
                {'error': 'Only company accounts can use this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )
        if request.user.phone_verified:
            return Response(
                {'error': 'Your email is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Expire any existing unverified phone OTPs for this user
        OTPVerification.objects.filter(
            user=request.user,
            otp_type='company_email',
            is_verified=False,
        ).update(expires_at=timezone.now())

        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=generate_otp(),
            otp_type='company_email',
            phone_number='',
            email=request.user.email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        try:
            send_company_email_otp_task.delay(otp.id)
        except Exception:
            send_company_email_otp_task(otp.id)

        response_data = {
            'message': 'A new OTP has been sent to your email address.',
            'otp_id': str(otp.id),
            'expires_at': otp.expires_at,
        }
        if settings.DEBUG:
            response_data['otp_code'] = otp.otp_code

        return Response(response_data, status=status.HTTP_200_OK)
