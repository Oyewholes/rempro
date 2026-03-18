from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import OTPValidateSerializer
from appone.models import OTPVerification, User, FreelancerProfile, CompanyProfile
from appone.utils import generate_otp, send_otp_sms
from appone.tasks import send_otp_task
from datetime import timedelta
from django.utils import timezone
from RemPro import settings
import re, random

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
        otp_code = generate_otp()

        # Create OTP record
        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=otp_code,
            otp_type='phone',
            phone_number=phone_number,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # This sends the SMS in the background without blocking the response
        try:
            send_otp_task.delay(otp.id)  # Async task

            response_data = {
                'message': 'OTP is being sent to your phone',
                'otp_id': str(otp.id),
                'expires_at': otp.expires_at,
            }

            # Only include OTP code in development mode
            if settings.DEBUG:
                response_data['otp_code'] = otp_code
                response_data['dev_note'] = 'OTP code shown only in DEBUG mode'

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Fallback: Try to send synchronously
            success = send_otp_sms(phone_number, otp_code)

            if success or settings.DEBUG:
                return Response({
                    'message': 'OTP sent successfully',
                    'otp_id': str(otp.id),
                    'expires_at': otp.expires_at,
                    'otp_code': otp_code if settings.DEBUG else None
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Failed to send OTP. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

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
            user = request.user

            # Update User.phone_verified
            user.phone_verified = True
            user.save(update_fields=['phone_verified'])

            # Update FreelancerProfile
            if hasattr(user, 'freelancer_profile'):
                profile = user.freelancer_profile
                profile.phone_number = otp.phone_number
                profile.phone_verified = True
                profile.save(update_fields=['phone_number', 'phone_verified'])
                profile.calculate_profile_completion()

            # Update CompanyProfile
            elif hasattr(user, 'company_profile'):
                company = user.company_profile
                company.phone_number = otp.phone_number
                company.phone_verified = True
                company.save(update_fields=['phone_number', 'phone_verified'])

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
    def verify_company_email_otp(self, request):
        """Verify company email OTP"""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_code = serializer.validated_data['otp_code']

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type='company_email',
                is_verified=False,
                expires_at__gte=timezone.now()
            )

            otp.is_verified = True
            otp.save()

            return Response({
                'message': 'Company email verified successfully',
            }, status=status.HTTP_200_OK)

        except OTPVerification.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)
