from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import JobApplicationSerializer, ContractSerializer, WorkspaceSerializer
from appone.models import JobApplication, Workspace, Contract


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

        freelancer = self.request.user.freelancer_profile
        if freelancer.verification_status != 'verified':
            raise serializers.ValidationError('Profile must be verified to apply for jobs')

        serializer.save(freelancer=freelancer)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update application status (Company only)"""
        if not hasattr(request.user, 'company_profile'):
            return Response({'error': 'Only companies can update application status'}, status=status.HTTP_403_FORBIDDEN)

        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if new_status not in dict(JobApplication.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        application.status = new_status
        application.save()

        return Response({
            'message': 'Application status updated',
            'application': JobApplicationSerializer(application).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def hire(self, request, pk=None):
        """Hire freelancer and create contract"""
        if not hasattr(request.user, 'company_profile'):
            return Response({'error': 'Only companies can hire freelancers'}, status=status.HTTP_403_FORBIDDEN)

        application = self.get_object()
        if application.job.company.user != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        if application.status == 'hired':
            return Response({'error': 'Freelancer already hired'}, status=status.HTTP_400_BAD_REQUEST)

        # Create contract
        contract_data = request.data
        contract = Contract.objects.create(
            job_application=application,
            company=application.job.company,
            freelancer=application.freelancer,
            start_date=contract_data.get('start_date'),
            monthly_rate=contract_data.get('monthly_rate'),
            currency=contract_data.get('currency', 'USD'),
            status='pending'
        )

        # Update application status
        application.status = 'hired'
        application.save()

        # Create workspace
        workspace = Workspace.objects.create(
            contract=contract,
            name=f"{application.job.title} - {application.freelancer.first_name}",
            description=f"Workspace for {application.job.title}"
        )

        return Response({
            'message': 'Freelancer hired successfully',
            'contract': ContractSerializer(contract).data,
            'workspace': WorkspaceSerializer(workspace).data
        }, status=status.HTTP_201_CREATED)
