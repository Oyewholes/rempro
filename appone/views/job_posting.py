from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import JobPostingSerializer, JobApplicationSerializer
from appone.models import JobPosting, JobApplication


class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'company_profile'):
            # Companies see their own jobs
            return JobPosting.objects.filter(company=self.request.user.company_profile)
        elif hasattr(self.request.user, 'freelancer_profile'):
            # Freelancers see active jobs
            return JobPosting.objects.filter(status='active')
        return JobPosting.objects.none()

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'company_profile'):
            raise serializers.ValidationError('Only companies can create job postings')
        serializer.save(company=self.request.user.company_profile)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a job posting"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        job.status = 'active'
        job.save()

        return Response({
            'message': 'Job published successfully',
            'job': JobPostingSerializer(job).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a job posting"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        job.status = 'closed'
        job.save()

        return Response({
            'message': 'Job closed successfully'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def applications(self, request, pk=None):
        """Get applications for a job"""
        job = self.get_object()
        if job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        applications = JobApplication.objects.filter(job=job)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)