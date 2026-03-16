from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import ContractSerializer
from appone.models import Contract

class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Contract.objects.filter(freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Contract.objects.filter(company=self.request.user.company_profile)
        return Contract.objects.none()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate contract"""
        contract = self.get_object()
        contract.status = 'active'
        contract.save()

        return Response({
            'message': 'Contract activated',
            'contract': ContractSerializer(contract).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete contract"""
        contract = self.get_object()
        contract.status = 'completed'
        contract.save()

        return Response({
            'message': 'Contract completed'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Terminate contract"""
        contract = self.get_object()
        contract.status = 'terminated'
        contract.save()

        return Response({
            'message': 'Contract terminated'
        }, status=status.HTTP_200_OK)
