from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import (
    AdminVerificationSerializer, FreelancerProfileSerializer,
    CompanyProfileSerializer
)
from appone.serializers import (
AdminCompanyVerificationSerializer, AdminConfirmMeetingSerializer
)
from appone.models import FreelancerProfile, CompanyProfile
from django.utils import timezone
from appone.utils import send_notification_email
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

    @action(detail=False, methods=['get'], url_path='company-proposed-dates')
    def company_proposed_dates(self, request):
        """
        List all companies that have submitted proposed meeting dates.
        Returns each company's name, email, proposed dates, and current
        verification status.
        """
        companies = CompanyProfile.objects.filter(
            proposed_meeting_dates__isnull=False,
        ).exclude(
            proposed_meeting_dates=[],
        )
        results = []
        for company in companies:
            results.append({
                'company_id': company.id,
                'company_name': company.company_name,
                'company_email': company.company_email,
                'proposed_meeting_dates': company.proposed_meeting_dates,
                'verification_status': company.verification_status,
                'meeting_scheduled_at': (
                    company.meeting_scheduled_at.isoformat()
                    if company.meeting_scheduled_at else None
                ),
            })
        return Response({
            'count': len(results),
            'results': results,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='confirm-meeting')
    def confirm_meeting(self, request):
        """
        Pick / confirm one of a company's proposed meeting dates.
        The selected date must:
          - Match one of the company's proposed_meeting_dates.
          - Be at least 24 hours in the future.
        On success the company is emailed with the confirmed date and
        meeting link.
        """
        serializer = AdminConfirmMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        company = serializer.validated_data['company']
        selected_date = serializer.validated_data['selected_date']
        meeting_link = serializer.validated_data['meeting_link']
        # Update the company profile
        company.meeting_scheduled_at = selected_date
        company.meeting_link = meeting_link
        company.verification_status = 'scheduled'
        company.save(update_fields=[
            'meeting_scheduled_at', 'meeting_link',
            'verification_status', 'updated_at',
        ])
        # Send confirmation email to the company
        formatted_date = selected_date.strftime('%A, %B %d, %Y at %I:%M %p UTC')
        email_sent = send_notification_email(
            company.company_email,
            'Verification Meeting Confirmed — Virtual Citizenship',
            (
                f'Dear {company.company_name},\n\n'
                f'Your verification meeting has been confirmed for:\n\n'
                f'    Date & Time: {formatted_date}\n'
                f'    Meeting Link: {meeting_link}\n\n'
                'Please make sure to join the meeting on time. '
                'If you need to reschedule, please contact the admin.\n\n'
                'Best regards,\n'
                'Virtual Citizenship Team'
            ),
        )
        if not email_sent:
            logger.warning(
                'confirm_meeting: email to %s failed — meeting was still confirmed',
                company.company_email,
            )
        return Response({
            'message': 'Meeting confirmed and email sent to the company.',
            'company_id': company.id,
            'company_name': company.company_name,
            'confirmed_date': selected_date.isoformat(),
            'meeting_link': meeting_link,
            'email_sent': email_sent,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-company')
    def verify_company(self, request):
        """
        Verify or reject a company profile.
        If verified:
          - verification_status → 'verified'
          - verified_at → now
          - verified_by → current admin user
          - user.is_verified → True
        If rejected:
          - verification_status → 'rejected'
        """
        serializer = AdminCompanyVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        company_id = serializer.validated_data['company_id']
        new_status = serializer.validated_data['verification_status']
        try:
            company = CompanyProfile.objects.get(id=company_id)
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)
        company.verification_status = new_status
        if new_status == 'verified':
            company.verified_at = timezone.now()
            company.verified_by = request.user
            company.user.is_verified = True
            company.user.save()
        elif new_status == 'rejected':
            company.user.is_verified = False
            company.user.save()
        company.save()
        # Notify the company by email
        status_label = 'approved' if new_status == 'verified' else 'rejected'
        send_notification_email(
            company.company_email,
            f'Company Verification {status_label.title()} — Virtual Citizenship',
            (
                    f'Dear {company.company_name},\n\n'
                    f'Your company verification has been {status_label}.\n\n'
                    + (
                        'You can now post jobs and hire freelancers on the platform.\n\n'
                        if new_status == 'verified' else
                        'If you believe this was in error, please contact support.\n\n'
                    )
                    + 'Best regards,\nVirtual Citizenship Team'
            ),
        )
        return Response({
            'message': f'Company verification {status_label}.',
            'profile': CompanyProfileSerializer(company).data,
        }, status=status.HTTP_200_OK)