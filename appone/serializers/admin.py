from datetime import timedelta

from dateutil.parser import parse as parse_dt
from django.utils import timezone
from rest_framework import serializers


class AdminConfirmMeetingSerializer(serializers.Serializer):
    company_id = serializers.UUIDField(required=True)
    selected_date = serializers.DateTimeField(required=True)
    meeting_link = serializers.URLField(required=True, max_length=500)

    def validate(self, data):
        from appone.models import CompanyProfile

        try:
            company = CompanyProfile.objects.get(id=data["company_id"])
        except CompanyProfile.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Company not found."})

        proposed = company.proposed_meeting_dates or []
        if not proposed:
            raise serializers.ValidationError(
                {"selected_date": "This company has not proposed any meeting dates."}
            )

        selected = data["selected_date"]
        matched = False
        for iso_str in proposed:
            proposed_dt = parse_dt(iso_str)
            if proposed_dt.tzinfo is None:
                proposed_dt = proposed_dt.replace(tzinfo=timezone.utc)
            if selected.tzinfo is None:
                selected = selected.replace(tzinfo=timezone.utc)

            if abs((selected - proposed_dt).total_seconds()) < 60:
                matched = True
                break

        if not matched:
            raise serializers.ValidationError(
                {
                    "selected_date": "The selected date does not match any of the company's proposed dates."
                }
            )

        now = timezone.now()
        if selected < now + timedelta(hours=24):
            raise serializers.ValidationError(
                {
                    "selected_date": "The selected date must be at least 24 hours in the future."
                }
            )

        data["company"] = company
        return data


class AdminCompanyVerificationSerializer(serializers.Serializer):
    company_id = serializers.UUIDField(required=True)
    verification_status = serializers.ChoiceField(
        choices=[("verified", "Verified"), ("rejected", "Rejected")]
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_company_id(self, value):
        from appone.models import CompanyProfile

        try:
            CompanyProfile.objects.get(id=value)
        except CompanyProfile.DoesNotExist:
            raise serializers.ValidationError("Company not found.")
        return value
