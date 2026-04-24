from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import JobApplication, JobPosting
from appone.serializers import JobApplicationSerializer, JobPostingSerializer
from appone.utils import APIResponse


@extend_schema(tags=["Job Postings"])
class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "title",
        "description",
        "required_skills",
        "job_type",
    ]
    ordering_fields = [
        "created_at",
        "salary_min",
        "salary_max",
    ]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "company_profile"):
            return JobPosting.objects.filter(company=user.company_profile)
        elif hasattr(user, "freelancer_profile"):
            return JobPosting.objects.filter(status="active")
        return JobPosting.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, "company_profile"):
            raise serializers.ValidationError("Only companies can create job postings")
        profile = user.company_profile
        if profile.verification_status != "verified":
            raise serializers.ValidationError(
                "Only verified companies can create job postings."
            )
        serializer.save(company=profile)

    @extend_schema(
        summary="Publish a job posting",
        description="Set a draft job posting to active so freelancers can see and apply.",
        responses={
            200: JobPostingSerializer,
            403: OpenApiResponse(description="Permission denied."),
        },
    )
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish a job posting."""
        job = self.get_object()
        if job.company.user != request.user:
            return APIResponse(
                message="Permission denied",
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
            )
        job.status = "active"
        job.save()
        return APIResponse(
            data={"job": JobPostingSerializer(job).data},
            message="Job published successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Close a job posting",
        description="Set a job posting to closed, preventing new applications.",
        responses={
            200: OpenApiResponse(description="Job closed."),
            403: OpenApiResponse(description="Permission denied."),
        },
    )
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Close a job posting."""
        job = self.get_object()
        if job.company.user != request.user:
            return APIResponse(
                message="Permission denied",
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
            )
        job.status = "closed"
        job.save()
        return APIResponse(
            message="Job closed successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="List applications for a job",
        description="Returns all applications submitted for this job posting (company only).",
        responses={
            200: JobApplicationSerializer(many=True),
            403: OpenApiResponse(description="Permission denied."),
        },
    )
    @action(detail=True, methods=["get"])
    def applications(self, request, pk=None):
        """Get applications for a job."""
        job = self.get_object()
        if job.company.user != request.user:
            return APIResponse(
                message="Permission denied",
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
            )
        applications = JobApplication.objects.filter(job=job)
        return APIResponse(
            data=JobApplicationSerializer(applications, many=True).data,
            message="Applications retrieved successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )
