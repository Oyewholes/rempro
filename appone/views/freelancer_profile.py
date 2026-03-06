import os, tempfile
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from appone.serializers import (
    FreelancerProfileSerializer, FreelancerProfileUpdateSerializer,
    FreelancerPublicProfileSerializer
)
from appone.models import FreelancerProfile, ProfileAccessLog
from appone.permissions import IsFreelancer
from appone.utils import verify_user_is_in_nigeria
from appone.tasks import upload_to_cloudinary_task
from RemPro import settings


# Allowed MIME types for CV uploads
_CV_ALLOWED_CONTENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

# Map MIME → file extension for the temp file
_MIME_TO_EXT = {
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
}


def _handle_file_upload(self, request, file_key, file_type, profile_field, allowed_types):
    """
    Shared upload logic: validate → write temp file → dispatch Celery task.

    Args:
        file_key:      The key in request.FILES, e.g. 'cv_file'
        file_type:     Passed to the task for Cloudinary folder/public_id
        profile_field: The FreelancerProfile field to update with the URL
        allowed_types: Set of accepted MIME type strings
    """
    try:
        profile = request.user.freelancer_profile
    except FreelancerProfile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

    uploaded_file = request.FILES.get(file_key)
    if not uploaded_file:
        return Response({'error': f'{file_key} is required'}, status=status.HTTP_400_BAD_REQUEST)

    if uploaded_file.content_type not in allowed_types:
        return Response(
            {'error': f'Invalid file type. Accepted: {", ".join(allowed_types)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > CV_MAX_SIZE_BYTES:
        return Response(
            {'error': 'File size must not exceed 10 MB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Derive extension from MIME type, fallback to original filename extension
    ext = _MIME_TO_EXT.get(uploaded_file.content_type) or \
          os.path.splitext(uploaded_file.name)[1] or '.bin'

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
    except OSError:
        return Response(
            {'error': 'Server error while preparing upload. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        upload_to_cloudinary_task.delay(str(profile.id), tmp_path, file_type, profile_field)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return Response(
            {'error': 'Upload queue unavailable. Please try again later.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {'message': f'Your {file_type.replace("_", " ")} is being processed and will be available shortly.'},
        status=status.HTTP_202_ACCEPTED,
    )


CV_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_client_ip(request) -> str:
    """
    Resolve the real client IP, honouring X-Forwarded-For when set
    (standard behind load balancers / proxies).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # The header may be a comma-separated list; the leftmost is the client
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')



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
        """
        Verify that the freelancer is physically located in Nigeria.

        Flow:
          1. Resolve the client's real IP (handles proxy / load-balancer
             X-Forwarded-For headers).
          2. Call verify_user_is_in_nigeria() which queries ipapi.co with
             automatic fallback to ip-api.com.
          3. If the country resolves to NG → mark location_verified = True
             and save the IP + country_code on the profile.
          4. If NOT Nigeria → return 403 with the detected country.
          5. If geolocation fails entirely → return 503 so the client
             can retry rather than being permanently blocked.
        """
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        if settings.DEBUG:
            ip_address = request.data.get('test_ip') #or _get_client_ip(request)
        else:
            ip_address = _get_client_ip(request)

        is_nigeria, location_data, message = verify_user_is_in_nigeria(ip_address)

        # ── Geolocation service completely unavailable ─────────────────────
        if location_data is None:
            return Response(
                {
                    'error': 'Location verification service is temporarily unavailable. '
                             'Please try again in a few minutes.',
                    'ip_address': ip_address,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # ── Outside Nigeria ─────────────────────────────────────────────────
        if not is_nigeria:

            return Response(
                {
                    'error': message,
                    'detected_location': {
                        'country': location_data.get('country_name'),
                        'country_code': location_data.get('country_code'),
                        'city': location_data.get('city'),
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Nigeria confirmed ───────────────────────────────────────────────
        profile.ip_address = ip_address
        profile.country_code = location_data.get('country_code', 'NGA')
        profile.location_verified = True
        profile.save(update_fields=['ip_address', 'country_code', 'location_verified'])
        profile.calculate_profile_completion()


        return Response(
            {
                'message': message,
                'location': {
                    'country': location_data.get('country_name'),
                    'country_code': location_data.get('country_code'),
                    'city': location_data.get('city'),
                    'region': location_data.get('region'),
                },
                'ip_address': ip_address,
                'profile_completion': profile.profile_completion_percentage,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'])
    def upload_cv(self, request):
        return _handle_file_upload(
            self, request,
            file_key='cv_file',
            file_type='cv',
            profile_field='cv_file',
            allowed_types=_CV_ALLOWED_CONTENT_TYPES,
        )
    @action(detail=False, methods=['post'])
    def upload_live_photo(self, request):
        return _handle_file_upload(
            self, request,
            file_key='live_photo',
            file_type='live_photo',
            profile_field='live_photo',
            allowed_types={'image/jpeg', 'image/png'},
        )

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
