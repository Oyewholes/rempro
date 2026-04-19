from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import (
    JobApplicationSerializer,
    ContractSerializer,
    HireFreelancerSerializer,
    UpdateJobApplicationStatusSerializer,
)
from appone.models import JobApplication, Contract, Workspace


@extend_schema(tags=['Job Applications'])
class JobApplicationViewSet(viewsets.ModelViewSet):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return JobApplication.objects.filter(freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return JobApplication.objects.filter(job__company=self.request.user.company_profile)
        return JobApplication.objects.none()

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'freelancer_profile'):
            raise serializers.ValidationError('Only freelancers can apply for jobs')
        serializer.save(freelancer=self.request.user.freelancer_profile)

    @extend_schema(
        summary='Hire freelancer',
        description='Company endpoint to hire a freelancer by accepting their application. Creates a contract and workspace.',
        request=HireFreelancerSerializer,
        responses={
            200: OpenApiResponse(description='Freelancer hired successfully.'),
            400: OpenApiResponse(description='Validation or missing data error.'),
            403: OpenApiResponse(description='Permission denied.'),
        },
    )
    @action(detail=True, methods=['post'])
    def hire(self, request, pk=None):
        """Hire a freelancer (creates contract)."""
        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        serializer = HireFreelancerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        monthly_rate = serializer.validated_data['monthly_rate']
        start_date = serializer.validated_data['start_date']

        application.status = 'hired'
        application.save()

        # Create contract
        contract = Contract.objects.create(
            job_application=application,
            company=application.job.company,
            freelancer=application.freelancer,
            monthly_rate=monthly_rate,
            start_date=start_date,
            status='active'
        )

        # Create workspace
        Workspace.objects.create(
            contract=contract,
            name=f"{application.job.title} - {application.freelancer.first_name}"
        )

        return Response({
            'message': 'Freelancer hired successfully',
            'contract': ContractSerializer(contract).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Update application status',
        description='Company endpoint to update the status of an application (e.g. shortlisted, rejected).',
        request=UpdateJobApplicationStatusSerializer,
        responses={
            200: OpenApiResponse(description='Status updated.'),
            400: OpenApiResponse(description='Invalid status.'),
            403: OpenApiResponse(description='Permission denied.'),
        },
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update application status."""
        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        serializer = UpdateJobApplicationStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        application.status = serializer.validated_data['status']
        application.save()

        return Response({
            'message': 'Application status updated',
            'application': JobApplicationSerializer(application).data
        }, status=status.HTTP_200_OK)
