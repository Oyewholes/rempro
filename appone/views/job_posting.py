from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import JobPostingSerializer, JobApplicationSerializer
from appone.models import JobPosting, JobApplication


@extend_schema(tags=['Job Postings'])
class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'company_profile'):
            return JobPosting.objects.filter(company=self.request.user.company_profile)
        elif hasattr(self.request.user, 'freelancer_profile'):
            return JobPosting.objects.filter(status='active')
        return JobPosting.objects.none()

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'company_profile'):
            raise serializers.ValidationError('Only companies can create job postings')
        serializer.save(company=self.request.user.company_profile)

    @extend_schema(
        summary='Publish a job posting',
        description='Set a draft job posting to active so freelancers can see and apply.',
        responses={
            200: JobPostingSerializer,
            403: OpenApiResponse(description='Permission denied.'),
        },
    )
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a job posting."""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        job.status = 'active'
        job.save()
        return Response(
            {'message': 'Job published successfully', 'job': JobPostingSerializer(job).data},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Close a job posting',
        description='Set a job posting to closed, preventing new applications.',
        responses={
            200: OpenApiResponse(description='Job closed.'),
            403: OpenApiResponse(description='Permission denied.'),
        },
    )
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a job posting."""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        job.status = 'closed'
        job.save()
        return Response({'message': 'Job closed successfully'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary='List applications for a job',
        description='Returns all applications submitted for this job posting (company only).',
        responses={
            200: JobApplicationSerializer(many=True),
            403: OpenApiResponse(description='Permission denied.'),
        },
    )
    @action(detail=True, methods=['get'])
    def applications(self, request, pk=None):
        """Get applications for a job."""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        applications = JobApplication.objects.filter(job=job)
        return Response(JobApplicationSerializer(applications, many=True).data)