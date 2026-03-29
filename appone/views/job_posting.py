from django.db.models import Q
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.permissions import (IsCompany, IsVerifiedCompany, IsOwnerOrReadOnly, IsFreelancerOrCompany)
from appone.serializers import JobPostingSerializer, JobApplicationSerializer, JobSearchQuerySerializer
from appone.models import JobPosting, JobApplication


class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer

    def get_permissions(self):
        """Map specific actions to different permission classes."""

        # Searching, Listing, and Reading: Open to authenticated Freelancers & Companies
        if self.action in ['list', 'retrieve', 'search']:
            return [IsAuthenticated(), IsFreelancerOrCompany()]

        # Creating jobs: Must be an authenticated VERIFIED company
        elif self.action == 'create':
            return [IsAuthenticated(), IsVerifiedCompany()]

        # Must be a company AND own the post (IsOwnerOrReadOnly handles ownership)
        elif self.action in ['update', 'partial_update', 'destroy', 'publish', 'close', 'applications']:
            return [IsAuthenticated(), IsCompany(), IsOwnerOrReadOnly()]

        return super().get_permissions()

    def get_queryset(self):
        if hasattr(self.request.user, 'company_profile'):
            # Companies see their own jobs
            return JobPosting.objects.filter(company=self.request.user.company_profile)
        elif hasattr(self.request.user, 'freelancer_profile'):
            # Freelancers see active jobs
            return JobPosting.objects.filter(status='active')
        return JobPosting.objects.none()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company_profile)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a job posting"""
        job = self.get_object()
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
        job.status = 'closed'
        job.save()

        return Response({
            'message': 'Job closed successfully'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def applications(self, request, pk=None):
        """Get applications for a job"""
        job = self.get_object()
        applications = JobApplication.objects.filter(job=job)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search active job postings"""
        query_serializer = JobSearchQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        queryset = JobPosting.objects.filter(status='active')

        # Filter by search string (title or description)
        q = data.get('q')
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(description__icontains=q))

        # Filter by job type
        job_type = data.get('job_type')
        if job_type:
            queryset = queryset.filter(job_type__iexact=job_type)

        # Filter by required country
        country = data.get('country')
        if country:
            queryset = queryset.filter(required_countries__contains=country)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Return serialized results
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)