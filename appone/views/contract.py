from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import Contract
from appone.serializers import ContractSerializer
from appone.utils import APIResponse


@extend_schema(tags=["Contracts"])
class ContractViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "freelancer_profile"):
            return Contract.objects.filter(
                freelancer=self.request.user.freelancer_profile
            )
        elif hasattr(self.request.user, "company_profile"):
            return Contract.objects.filter(company=self.request.user.company_profile)
        return Contract.objects.none()

    @extend_schema(
        summary="Terminate a contract",
        description="Company endpoint to terminate an active contract.",
        responses={
            200: OpenApiResponse(description="Contract terminated."),
            403: OpenApiResponse(description="Permission denied."),
        },
    )
    @action(detail=True, methods=["post"])
    def terminate(self, request, pk=None):
        """Terminate a contract."""
        contract = self.get_object()
        if contract.company.user != request.user:
            return APIResponse(
                message="Permission denied",
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
            )

        contract.status = "terminated"
        contract.end_date = timezone.now().date()
        contract.save()

        return APIResponse(
            data={"contract": ContractSerializer(contract).data},
            message="Contract terminated successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )
