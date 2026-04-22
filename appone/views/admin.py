from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import (
    AdminVerificationSerializer,
    FreelancerProfileSerializer,
    CompanyProfileSerializer,
    AdminConfirmMeetingSerializer,
    AdminCompanyVerificationSerializer,
)
from appone.models import FreelancerProfile, CompanyProfile
from django.utils import timezone
from appone.permissions import IsAdmin


@extend_schema(tags=['Admin'])
class AdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary='Verify freelancer (admin)',
        description='Admin endpoint to verify or reject a freelancer profile.',
        request=AdminVerificationSerializer,
        responses={
            200: OpenApiResponse(description='Freelancer verification updated.'),
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Freelancer not found.'),
        },
    )
    @action(detail=False, methods=['post'])
    def verify_freelancer(self, request):
        """Verify freelancer profile"""
        serializer = AdminVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        freelancer_id = serializer.validated_data['freelancer_id']

        try:
            profile = FreelancerProfile.objects.get(id=freelancer_id)
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Freelancer not found'}, status=status.HTTP_404_NOT_FOUND)

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

    @extend_schema(
        summary='Get pending freelancer verifications',
        description='Returns all freelancer profiles with pending verification status.',
        responses={200: FreelancerProfileSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def pending_verifications(self, request):
        """Get pending freelancer verifications"""
        freelancers = FreelancerProfile.objects.filter(verification_status='pending')
        serializer = FreelancerProfileSerializer(freelancers, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Get pending company verifications',
        description='Returns all company profiles with pending or scheduled verification status.',
        responses={200: CompanyProfileSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def pending_companies(self, request):
        """Get pending company verifications"""
        companies = CompanyProfile.objects.filter(verification_status__in=['pending', 'scheduled'])
        serializer = CompanyProfileSerializer(companies, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Get companies with proposed dates',
        description='Returns all company profiles that have submitted proposed meeting dates.',
        responses={200: CompanyProfileSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='company-proposed-dates')
    def company_proposed_dates(self, request):
        """Get companies with proposed dates"""
        companies = CompanyProfile.objects.exclude(proposed_meeting_dates=[])
        serializer = CompanyProfileSerializer(companies, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Confirm verification meeting',
        description='Admin selects one of the 3 proposed dates for a company.',
        request=AdminConfirmMeetingSerializer,
        responses={
            200: OpenApiResponse(description='Meeting confirmed.'),
            400: OpenApiResponse(description='Validation error.'),
        },
    )
    @action(detail=False, methods=['post'], url_path='confirm-meeting')
    def confirm_meeting(self, request):
        """Confirm a verification meeting date"""
        serializer = AdminConfirmMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        company = serializer.validated_data['company']
        company.meeting_scheduled_at = serializer.validated_data['selected_date']
        company.meeting_link = serializer.validated_data['meeting_link']
        company.verification_status = 'scheduled'
        company.save()

        # TODO: Send email notification to company

        return Response({
            'message': 'Meeting confirmed successfully',
            'company': CompanyProfileSerializer(company).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Verify/Reject company',
        description='Admin manually verifies or rejects a company profile.',
        request=AdminCompanyVerificationSerializer,
        responses={
            200: OpenApiResponse(description='Company status updated.'),
            400: OpenApiResponse(description='Validation error.'),
        },
    )
    @action(detail=False, methods=['post'], url_path='verify-company')
    def verify_company(self, request):
        """Verify or reject a company"""
        serializer = AdminCompanyVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        company_id = serializer.validated_data['company_id']
        profile = CompanyProfile.objects.get(id=company_id)

        profile.verification_status = serializer.validated_data['verification_status']
        if profile.verification_status == 'verified':
            profile.verified_at = timezone.now()
            profile.verified_by = request.user
            profile.user.is_verified = True
            profile.user.save()

        profile.save()

        return Response({
            'message': 'Company status updated',
            'company': CompanyProfileSerializer(profile).data
        }, status=status.HTTP_200_OK)
