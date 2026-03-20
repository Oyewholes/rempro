from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import (
    CompanyProfileSerializer, CompanyProfileUpdateSerializer,
    ScheduleMeetingSerializer, ProposedMeetingDatesSerializer
)
from appone.models import CompanyProfile
from appone.permissions import IsCompany
from django.utils import timezone

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

    @action(detail=False, methods=['post'], url_path='propose-meeting-dates')
    def propose_meeting_dates(self, request):
        """
               Submit exactly 3 proposed meeting date/time options for the admin
               verification meeting.

               Rules:
                 - Exactly 1-3 datetimes are required.
                 - All datetimes must be in the future (past datetimes are rejected individually).
                 - All datetimes must be unique (no duplicates).
                 - The company must not already be verified or rejected.
                 - Submitting again overwrites the previous proposal.

               Request body:
                   {
                       "proposed_dates": [
                           "2026-04-10T09:00:00Z",
                           "2026-04-11T14:00:00Z",
                           "2026-04-12T11:30:00Z"
                       ]
                   }

               Response 200:
                   {
                       "message": "Your proposed meeting dates have been submitted. ...",
                       "proposed_dates": ["2026-04-10T09:00:00Z", ...],
                       "verification_status": "scheduled"
                   }
        """
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

            # Do not allow re-submission once the company is already verified / rejected
        if profile.verification_status in ('verified', 'rejected'):
            return Response(
                {
                    'error': (
                        f"Your company is already '{profile.verification_status}'. "
                        "Meeting dates can only be proposed while the status is pending or scheduled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProposedMeetingDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Persist the 3 proposed dates as ISO strings in the JSONField
        proposed = serializer.validated_data['proposed_dates']
        profile.proposed_meeting_dates = [dt.isoformat() for dt in proposed]
        profile.verification_status = 'scheduled'
        profile.save(update_fields=['proposed_meeting_dates', 'verification_status', 'updated_at'])

        return Response(
            {
                'message': (
                    "Your proposed meeting dates have been submitted. "
                    "An admin will confirm one of the slots and you will be notified by email."
                ),
                'proposed_dates': profile.proposed_meeting_dates,
                'verification_status': profile.verification_status,
            },
            status=status.HTTP_200_OK,
        )

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