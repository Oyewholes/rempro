from rest_framework import serializers

from appone.models import JobApplication, JobPosting


class JobPostingSerializer(serializers.ModelSerializer):
    """Serializer for Job Posting creation and details."""

    company_name = serializers.ReadOnlyField(source="company.company_name")

    class Meta:
        model = JobPosting
        fields = "__all__"
        read_only_fields = ("id", "company", "created_at", "updated_at")

    def validate(self, data):
        if data["salary_min"] >= data["salary_max"]:
            raise serializers.ValidationError(
                "Minimum salary must be less than maximum salary."
            )
        return data


class JobApplicationSerializer(serializers.ModelSerializer):
    """Serializer for Job Application creation and details."""

    freelancer_name = serializers.ReadOnlyField(source="freelancer.__str__")
    job_title = serializers.ReadOnlyField(source="job.title")

    class Meta:
        model = JobApplication
        fields = "__all__"
        read_only_fields = (
            "id",
            "freelancer",
            "status",
            "applied_at",
            "updated_at",
        )

    def validate_freelancer(self, value):
        if value.verification_status != "verified":
            raise serializers.ValidationError(
                "Only verified freelancers can apply for jobs."
            )
        return value

    def validate_job(self, value):
        if value.status != "active":
            raise serializers.ValidationError(
                "You can only apply to active job postings."
            )
        return value


class HireFreelancerSerializer(serializers.Serializer):
    """Serializer for hiring a freelancer."""

    monthly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True
    )
    start_date = serializers.DateField(required=True)


class UpdateJobApplicationStatusSerializer(serializers.Serializer):
    """Serializer for updating job application status."""

    status = serializers.ChoiceField(
        choices=JobApplication.STATUS_CHOICES, required=True
    )
