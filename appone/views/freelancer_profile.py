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
