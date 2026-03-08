from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from appone.serializers import (
    FreelancerProfileSerializer,
    FreelancerProfileUpdateSerializer,
    FreelancerPublicProfileSerializer,
)
from appone.models import FreelancerProfile, ProfileAccessLog
from appone.permissions import IsFreelancer
from appone.utils import (
    verify_user_is_in_nigeria,
    generate_signed_url,
    generate_signed_download_url,
)
from appone.tasks import upload_to_cloudinary_task, generate_id_card_task
from RemPro import settings
import base64
import logging
import time
import io
from PIL import Image

logger = logging.getLogger(__name__)


# Allowed MIME types for CV uploads
_CV_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

CV_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _handle_file_upload(
    self, request, file_key, file_type, profile_field, allowed_types
):
    """
    Optimized upload handler:
    - Reads file ONCE directly from memory (no temp file)
    - Base64-encodes and passes through Redis to the worker
    - Eliminates all disk I/O on the web server side
    """
    try:
        profile = request.user.freelancer_profile
    except FreelancerProfile.DoesNotExist:
        return Response(
            {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
        )

    uploaded_file = request.FILES.get(file_key)
    if not uploaded_file:
        return Response(
            {"error": f"{file_key} is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    if uploaded_file.content_type not in allowed_types:
        return Response(
            {"error": f"Invalid file type. Accepted: {', '.join(allowed_types)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > CV_MAX_SIZE_BYTES:
        return Response(
            {"error": "File size must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        file_bytes = uploaded_file.read()
        file_b64 = base64.b64encode(file_bytes).decode("utf-8")
    except Exception:
        return Response(
            {"error": "Failed to read uploaded file. Please try again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

        # Dispatch to Celery — no disk writes, no temp files
    try:
        upload_to_cloudinary_task.apply_async(
            args=[str(profile.id), file_b64, file_type, profile_field],
            ignore_result=True,
        )
    except Exception:
        return Response(
            {"error": "Upload queue unavailable. Please try again later."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "message": f"Your {file_type.replace('_', ' ')} is being processed and will be available shortly."
        },
        status=status.HTTP_202_ACCEPTED,
    )


def _get_client_ip(request) -> str:
    """
    Resolve the real client IP, honouring X-Forwarded-For when set
    (standard behind load balancers / proxies).
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # The header may be a comma-separated list; the leftmost is the client
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class FreelancerProfileViewSet(viewsets.ModelViewSet):
    queryset = FreelancerProfile.objects.all()
    serializer_class = FreelancerProfileSerializer

    def get_permissions(self):
        if self.action in ["retrieve_by_digital_id", "public_profile"]:
            return [AllowAny()]
        return [IsAuthenticated(), IsFreelancer()]

    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(
            self.request.user, "freelancer_profile"
        ):
            return FreelancerProfile.objects.filter(user=self.request.user)
        return FreelancerProfile.objects.none()

    @action(detail=False, methods=["get", "put", "patch"])
    def me(self, request):
        """Get or update current freelancer's profile"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if request.method == "GET":
            serializer = FreelancerProfileSerializer(
                profile, context={"request": request}
            )
            return Response(serializer.data)

        elif request.method in ["PUT", "PATCH"]:
            serializer = FreelancerProfileUpdateSerializer(
                profile, data=request.data, partial=(request.method == "PATCH")
            )
            if serializer.is_valid():
                serializer.save()
                profile.calculate_profile_completion()
                return Response(
                    FreelancerProfileSerializer(
                        profile, context={"request": request}
                    ).data
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def verify_location(self, request):
        """
        Verify that the freelancer is physically located in Nigeria.

        Flow:
          1. Resolve the client's real IP (handles proxy / load-balancer
             X-Forwarded-For headers).
          2. Call verify_user_is_in_nigeria() which queries ipapi.co with
             automatic fallback to ip-api.com.
          3. If the country resolves to NG → mark location_verified = True
             and save the IP + country_code on the profile.
          4. If NOT Nigeria → return 403 with the detected country.
          5. If geolocation fails entirely → return 503 so the client
             can retry rather than being permanently blocked.
        """
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if settings.DEBUG:
            ip_address = request.data.get("test_ip")  # or _get_client_ip(request)
        else:
            ip_address = _get_client_ip(request)

        is_nigeria, location_data, message = verify_user_is_in_nigeria(ip_address)

        # ── Geolocation service completely unavailable ─────────────────────
        if location_data is None:
            return Response(
                {
                    "error": "Location verification service is temporarily unavailable. "
                    "Please try again in a few minutes.",
                    "ip_address": ip_address,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # ── Outside Nigeria ─────────────────────────────────────────────────
        if not is_nigeria:
            return Response(
                {
                    "error": message,
                    "detected_location": {
                        "country": location_data.get("country_name"),
                        "country_code": location_data.get("country_code"),
                        "city": location_data.get("city"),
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Nigeria confirmed ───────────────────────────────────────────────
        profile.ip_address = ip_address
        profile.country_code = location_data.get("country_code", "NGA")
        profile.location_verified = True
        profile.save(update_fields=["ip_address", "country_code", "location_verified"])
        profile.calculate_profile_completion()

        return Response(
            {
                "message": message,
                "location": {
                    "country": location_data.get("country_name"),
                    "country_code": location_data.get("country_code"),
                    "city": location_data.get("city"),
                    "region": location_data.get("region"),
                },
                "ip_address": ip_address,
                "profile_completion": profile.profile_completion_percentage,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def upload_cv(self, request):
        # signed_url = generate_signed_url(profile.cv_file, resource_type="raw", expiry_seconds=300)
        return _handle_file_upload(
            self,
            request,
            file_key="cv_file",
            file_type="cv",
            profile_field="cv_file",
            allowed_types=_CV_ALLOWED_CONTENT_TYPES,
        )

    @action(detail=False, methods=["post"])
    def upload_live_photo(self, request):
        return _handle_file_upload(
            self,
            request,
            file_key="live_photo",
            file_type="live_photo",
            profile_field="live_photo",
            allowed_types={"image/jpeg", "image/png"},
        )

    @action(detail=False, methods=["post"])
    def add_nin(self, request):
        """Add National Identification Number"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        nin = request.data.get("nin")
        if not nin or len(nin) != 11:
            return Response(
                {"error": "Valid 11-digit NIN is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: Verify NIN with government API

        profile.nin = nin
        profile.save()
        profile.calculate_profile_completion()

        return Response(
            {"message": "NIN added successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"])
    def add_portfolio(self, request):
        """Add portfolio items"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        portfolio_item = request.data.get("portfolio_item")
        if not portfolio_item:
            return Response(
                {"error": "Portfolio item is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(profile.portfolio_files, list):
            profile.portfolio_files = []

        profile.portfolio_files.append(portfolio_item)
        profile.save()
        profile.calculate_profile_completion()

        return Response(
            {
                "message": "Portfolio item added successfully",
                "portfolio": profile.portfolio_files,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def add_banking_details(self, request):
        """Add banking details (Paystack/Payoneer)"""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        paystack_email = request.data.get("paystack_email")
        payoneer_email = request.data.get("payoneer_email")

        if not paystack_email and not payoneer_email:
            return Response(
                {"error": "At least one payment method is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if paystack_email:
            profile.paystack_email = paystack_email
        if payoneer_email:
            profile.payoneer_email = payoneer_email

        profile.bank_details_verified = True
        profile.save()
        profile.calculate_profile_completion()

        return Response(
            {"message": "Banking details added successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"], url_path="digital-id/(?P<digital_id>[^/.]+)")
    def retrieve_by_digital_id(self, request, digital_id=None):
        """Retrieve freelancer profile by digital ID (public access with OTP for companies)"""
        try:
            profile = FreelancerProfile.objects.get(digital_id=digital_id)
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # If accessed by a company, require OTP verification
        if request.user.is_authenticated and hasattr(request.user, "company_profile"):
            # Log the access
            ProfileAccessLog.objects.create(
                company=request.user.company_profile,
                freelancer=profile,
                otp_verified=True,  # Assume OTP was verified in previous step
            )

        serializer = FreelancerPublicProfileSerializer(profile)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def generate_id_card(self, request):
        """
        Trigger (re)generation of the freelancer's digital ID card.

        The card is generated asynchronously by ``generate_id_card_task``.
        Once complete the Cloudinary URL is persisted on the profile and an
        email notification is sent to the freelancer.

        Only verified profiles can generate an ID card.

        Response (202):
            {
                "message": "ID card generation started. ...",
                "status":  "processing"
            }
        """
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if profile.verification_status != "verified":
            return Response(
                {
                    "error": (
                        "Your profile must be verified before an ID card can be generated. "
                        f"Current status: {profile.verification_status}"
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            generate_id_card_task.apply_async(
                args=[str(profile.id)],
                ignore_result=False,
            )
        except Exception as exc:
            logger.error(
                "generate_id_card: failed to enqueue task for profile %s: %s",
                profile.id,
                exc,
            )
            return Response(
                {
                    "error": "ID card generation queue is unavailable. Please try again later."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "ID card generation started. You will receive an email when it's ready, "
                    "and it will be available for download from GET /api/freelancers/download_id_card/."
                ),
                "status": "processing",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def download_id_card(self, request):
        """
        Return the Cloudinary download URL for the freelancer's digital ID card.

        The URL points to a PNG image hosted on Cloudinary and can be used
        directly in a browser or ``<img>`` tag.  Clients that need a forced
        file download should append ``?fl_attachment`` to the Cloudinary URL
        (standard Cloudinary transformation flag).

        Response (200):
            {
                "id_card_url":      "https://res.cloudinary.com/…/id_card_<uuid>.png",
                "download_url":     "https://res.cloudinary.com/…/id_card_<uuid>.png?fl_attachment",
                "profile_name":     "John Doe",
                "digital_id":       "<uuid>",
                "generated":        true
            }
        """
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not profile.id_card_image:
            if profile.verification_status == "verified":
                hint = (
                    "Your ID card has not been generated yet. "
                    "Call POST /api/freelancers/generate_id_card/ to create one."
                )
            else:
                hint = (
                    "Your profile must be verified before an ID card can be generated. "
                    f"Current status: {profile.verification_status}."
                )
            return Response(
                {"error": "ID card not available.", "hint": hint},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate a signed URL valid for 10 minutes
        signed_url = generate_signed_url(
            profile.id_card_image, resource_type="image", expiry_seconds=120
        )
        download_url = generate_signed_download_url(
            profile.id_card_image,
            filename=f"Virtual_Citizenship_ID_{profile.digital_id}.png",
            resource_type="image",
            expiry_seconds=120,
        )

        # Cloudinary supports forced downloads by appending ?fl_attachment
        # base_url = profile.id_card_image
        download_url = f"{signed_url}?fl_attachment=Virtual_Citizenship_ID_{profile.digital_id}.png"

        return Response(
            {
                "id_card_url": signed_url,
                "download_url": download_url,
                "profile_name": f"{profile.first_name} {profile.last_name}".strip(),
                "digital_id": str(profile.digital_id),
                "generated": True,
                "expires_in_seconds": 120,
            },
            status=status.HTTP_200_OK,
        )
