from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from dateutil.parser import parse as parse_dt


class AdminConfirmMeetingSerializer(serializers.Serializer):
    """
    Serializer for admin to pick one of a company's proposed meeting dates.

    Validation rules:
        1. company_id must reference an existing CompanyProfile.
        2. selected_date must exactly match one of the company's proposed_meeting_dates.
        3. selected_date must be at least 24 hours in the future.
    """
    company_id = serializers.IntegerField(required=True)
    selected_date = serializers.DateTimeField(required=True)
    meeting_link = serializers.URLField(required=True, max_length=500)

    def validate(self, data):
        from appone.models import CompanyProfile

        # ── 1. Fetch company ──────────────────────────────────────────────
        try:
            company = CompanyProfile.objects.get(id=data['company_id'])
        except CompanyProfile.DoesNotExist:
            raise serializers.ValidationError({'company_id': 'Company not found.'})

        # ── 2. Verify selected_date is among proposed dates ────────────────
        proposed = company.proposed_meeting_dates or []
        if not proposed:
            raise serializers.ValidationError(
                {'selected_date': 'This company has not proposed any meeting dates.'}
            )

        # Normalise both sides to offset-aware UTC for comparison
        selected = data['selected_date']
        matched = False
        for iso_str in proposed:
            proposed_dt = parse_dt(iso_str)
            # If naive, assume UTC
            if proposed_dt.tzinfo is None:
                proposed_dt = proposed_dt.replace(tzinfo=timezone.utc)
            if selected.tzinfo is None:
                selected = selected.replace(tzinfo=timezone.utc)
            # Allow a 1-minute tolerance to deal with formatting differences
            if abs((selected - proposed_dt).total_seconds()) < 60:
                matched = True
                break

        if not matched:
            raise serializers.ValidationError({
                'selected_date': (
                    'The selected date does not match any of the company\'s proposed dates. '
                    f'Proposed dates: {proposed}'
                )
            })

        # ── 3. Must be at least 24 hours in the future ─────────────────────
        now = timezone.now()
        if selected < now + timedelta(hours=24):
            raise serializers.ValidationError({
                'selected_date': (
                    'The selected date must be at least 24 hours in the future. '
                    f'Current server time: {now.isoformat()}'
                )
            })

        # Attach the company object so the view doesn't need to re-fetch
        data['company'] = company
        return data


class AdminCompanyVerificationSerializer(serializers.Serializer):
    """
    Serializer for admin to verify or reject a company profile.
    """
    company_id = serializers.IntegerField(required=True)
    verification_status = serializers.ChoiceField(
        choices=[('verified', 'Verified'), ('rejected', 'Rejected')]
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_company_id(self, value):
        from appone.models import CompanyProfile
        try:
            CompanyProfile.objects.get(id=value)
        except CompanyProfile.DoesNotExist:
            raise serializers.ValidationError('Company not found.')
        return value

