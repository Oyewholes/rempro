from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from appone.models import Payment
from appone.serializers import PaymentSerializer


@extend_schema(tags=["Payments"])
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "freelancer_profile"):
            return Payment.objects.filter(
                contract__freelancer=self.request.user.freelancer_profile
            )
        elif hasattr(self.request.user, "company_profile"):
            return Payment.objects.filter(
                contract__company=self.request.user.company_profile
            )
        return Payment.objects.none()

    @extend_schema(
        summary="Create a payment",
        description="Initiate a payment.",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Create payment with tax calculations"""
        if not hasattr(self.request.user, "company_profile"):
            raise serializers.ValidationError(
                "Only companies can initiate payments",
            )

        contract = serializer.validated_data["contract"]
        amount = serializer.validated_data["amount"]

        # Calculate taxes
        platform_tax = (amount * contract.platform_tax_rate) / 100
        dwelling_tax = (amount * contract.dwelling_country_tax_rate) / 100
        work_tax = (amount * contract.work_country_tax_rate) / 100
        net_amount = amount - (platform_tax + dwelling_tax + work_tax)

        serializer.save(
            platform_tax=platform_tax,
            dwelling_country_tax=dwelling_tax,
            work_country_tax=work_tax,
            net_amount=net_amount,
            transaction_reference=(
                f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{contract.id}",
            ),
        )

    @extend_schema(
        summary="Process payment",
        description="Process a pending payment.",
        responses={
            200: OpenApiResponse(description="Payment processed."),
            400: OpenApiResponse(description="Payment already processed."),
        },
    )
    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """Process payment"""
        payment = self.get_object()

        if payment.status != "pending":
            return Response(
                {"error": "Payment already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: Integrate with payment gateway (Paystack, Stripe, etc.)

        payment.status = "completed"
        payment.processed_at = timezone.now()
        payment.save()

        return Response(
            {
                "message": "Payment processed successfully",
                "payment": PaymentSerializer(payment).data,
            },
            status=status.HTTP_200_OK,
        )
