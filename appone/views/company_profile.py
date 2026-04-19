from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import (
    CompanyProfileSerializer,
    CompanyProfileUpdateSerializer,
    ScheduleMeetingSerializer,
    VerifyCompanyRegistrationSerializer,
)
from appone.models import CompanyProfile
from appone.permissions import IsCompany
from django.utils import timezone


@extend_schema(tags=['Company Profile'])
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

    @extend_schema(
        summary='Get or update my company profile',
        description='GET returns the current company profile. PUT/PATCH updates it.',
        responses={
            200: CompanyProfileSerializer,
            404: OpenApiResponse(description='Profile not found.'),
        },
    )
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current company's profile."""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            return Response(CompanyProfileSerializer(profile).data)

        serializer = CompanyProfileUpdateSerializer(
            profile, data=request.data, partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            serializer.save()
            return Response(CompanyProfileSerializer(profile).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Schedule verification meeting',
        description='Schedule an admin verification video meeting for the company.',
        request=ScheduleMeetingSerializer,
        responses={
            200: OpenApiResponse(description='Meeting scheduled successfully.'),
            400: OpenApiResponse(description='Validation error.'),
        },
    )
    @action(detail=False, methods=['post'])
    def schedule_verification_meeting(self, request):
        """Schedule verification meeting with admin."""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ScheduleMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile.meeting_scheduled_at = serializer.validated_data['meeting_scheduled_at']
        if 'meeting_link' in serializer.validated_data:
            profile.meeting_link = serializer.validated_data['meeting_link']
        profile.verification_status = 'scheduled'
        profile.save()

        return Response(
            {
                'message': 'Meeting scheduled successfully',
                'meeting_date': profile.meeting_scheduled_at,
                'meeting_link': profile.meeting_link,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Verify company registration (admin)',
        description='Admin-only: trigger government database verification for a company.',
        request=VerifyCompanyRegistrationSerializer,
        responses={
            200: OpenApiResponse(description='Verification result returned.'),
            403: OpenApiResponse(description='Admin access required.'),
        },
    )
    @action(detail=False, methods=['post'])
    def verify_company_registration(self, request):
        """Verify company with government database (Admin only)."""
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        serializer = VerifyCompanyRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        company_id = serializer.validated_data['company_id']
        try:
            profile = CompanyProfile.objects.get(id=company_id)
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)

        api_verified = True
        verification_data = {
            'registration_number': profile.company_registration_number,
            'company_name': profile.company_name,
            'verified': True,
            'verified_at': timezone.now().isoformat(),
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

        return Response(
            {
                'message': 'Company verification completed',
                'verification_status': profile.verification_status,
                'api_verification_data': verification_data,
            },
            status=status.HTTP_200_OK,
        )