from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import (
    AdminVerificationSerializer, FreelancerProfileSerializer,
    CompanyProfileSerializer
)
from appone.models import FreelancerProfile, CompanyProfile
from django.utils import timezone
from appone.permissions import IsAdmin


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
