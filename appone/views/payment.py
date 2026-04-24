import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from appone.models import Payment
from appone.serializers import PaymentSerializer
from appone.utils import APIResponse


@extend_schema(tags=["Payments"])
class PaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
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
        if contract.company != self.request.user.company_profile:
            raise serializers.ValidationError("You do not own this contract.")
        if (
            contract.payment_type == "one_time"
            and contract.payments.filter(
                status__in=["completed", "processing", "pending"]
            ).exists()
        ):
            raise serializers.ValidationError(
                "A one-time contract can only have one payment."
            )
        if contract.payment_type == "monthly":
            amount = contract.monthly_rate
        elif contract.payment_type == "one_time":
            amount = contract.total_contract_value
        else:
            amount = serializer.validated_data.get("amount")
            if not amount:
                raise serializers.ValidationError(
                    "You must specify the milestone amount."
                )

        platform_tax = (amount * contract.platform_tax_rate) / 100
        dwelling_tax = (amount * contract.dwelling_country_tax_rate) / 100
        work_tax = (amount * contract.work_country_tax_rate) / 100
        net_amount = amount - (platform_tax + dwelling_tax + work_tax)

        serializer.save(
            platform_tax=platform_tax,
            dwelling_country_tax=dwelling_tax,
            work_country_tax=work_tax,
            net_amount=net_amount,
            transaction_reference=f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{contract.id}",
        )

    @extend_schema(
        summary="Process payment",
        description="Initialize Paystack transaction and return checkout URL.",
        responses={
            200: OpenApiResponse(description="Returns Paystack authorization URL."),
            400: OpenApiResponse(description="Payment already processed or failed."),
        },
    )
    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """Process payment"""
        from appone.utils.payment import process_paystack_payment

        payment = self.get_object()
        if (
            not hasattr(request.user, "company_profile")
            or payment.contract.company != request.user.company_profile
        ):
            return APIResponse(
                message="Only the hiring company can initiate the payment process.",
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
            )

        if payment.status not in ["pending", "failed"]:
            return APIResponse(
                message="Payment is already processing or completed.",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )
        work_country_code = payment.contract.company.country
        dwelling_country_code = payment.contract.freelancer.country_code

        paystack_response = process_paystack_payment(
            payment,
            work_country_code=work_country_code,
            dwelling_country_code=dwelling_country_code,
        )
        if not paystack_response or not paystack_response.get("status"):
            payment.status = "failed"
            payment.save(update_fields=["status"])
            return APIResponse(
                message="Failed to initialize payment with Paystack.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                status="error",
            )
        payment.status = "processing"
        payment.save(update_fields=["status"])
        return APIResponse(
            data={"authorization_url": paystack_response["data"]["authorization_url"]},
            message="Payment initialized successfully. Redirect to complete payment.",
            status_code=status.HTTP_200_OK,
            status="success",
        )


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        paystack_signature = request.headers.get("x-paystack-signature")
        if not paystack_signature:
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
                message="Invalid Paystack request",
            )
        secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
        body = request.body
        expected_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()
        if expected_signature != paystack_signature:
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
                message="Invalid Paystack request",
            )
        event_data = json.loads(body)
        event = event_data.get("event")
        data = event_data.get("data", {})
        if event == "charge.success":
            reference = data.get("reference")
            try:
                payment = Payment.objects.get(transaction_reference=reference)

                if payment.status in ["processing", "pending"]:
                    payment.status = "completed"
                    payment.processed_at = timezone.now()
                    payment.save(update_fields=["status", "processed_at"])

            except Payment.DoesNotExist:
                pass

        return APIResponse(
            status_code=status.HTTP_200_OK,
            status="success",
            message="",
        )
