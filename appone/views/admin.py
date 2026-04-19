from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import (
    AdminVerificationSerializer,
    FreelancerProfileSerializer,
    CompanyProfileSerializer
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
