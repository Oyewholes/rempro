from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from appone.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
)
from appone.utils import APIResponse


@extend_schema(tags=["Authentication"])
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        description=(
            "Creates a new User account along with the corresponding "
            "FreelancerProfile or CompanyProfile. Also creates a pending "
            "OTPVerification record and triggers an SMS to the supplied "
            "phone number via Celery."
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Registration successful — tokens returned."
            ),
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @extend_schema(
        summary="Register a new freelancer",
        request=RegisterSerializer,
        responses={201: OpenApiResponse(description="Registration successful.")},
    )
    @action(detail=False, methods=["post"])
    def register_freelancer(self, request):
        """Register a freelancer user."""
        serializer = RegisterSerializer(
            data=request.data,
            context={
                "expected_user_type": "freelancer",
            },
        )
        return self._handle_registration(serializer, "phone number")

    @extend_schema(
        summary="Register a new company",
        request=RegisterSerializer,
        responses={201: OpenApiResponse(description="Registration successful.")},
    )
    @action(detail=False, methods=["post"])
    def register_company(self, request):
        serializer = RegisterSerializer(
            data=request.data, context={"expected_user_type": "company"}
        )
        return self._handle_registration(serializer, "email")

    @extend_schema(
        summary="Register a new admin",
        request=RegisterSerializer,
        responses={201: OpenApiResponse(description="Registration successful.")},
    )
    @action(detail=False, methods=["post"])
    def register_admin(self, request):
        serializer = RegisterSerializer(
            data=request.data, context={"expected_user_type": "admin"}
        )
        return self._handle_registration(serializer, "phone number")

    @extend_schema(
        summary="Login",
        description="Authenticate with email and password. Returns JWT access and refresh tokens.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Login successful — tokens returned."),
            400: OpenApiResponse(description="Invalid credentials."),
        },
    )
    @action(detail=False, methods=["post"])
    def login(self, request):
        """Login user and receive JWT tokens."""
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)

            return APIResponse(
                data={
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "user_type": user.user_type,
                        "is_verified": user.is_verified,
                    },
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status_code=status.HTTP_200_OK,
                status="success",
                message="Login successful",
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Logout",
        description="logout the user.",
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid or missing refresh token."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def logout(self, request):
        """Logout user."""
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return APIResponse(
                message="Logged out successfully.",
                status_code=status.HTTP_205_RESET_CONTENT,
                status="success",
            )
        except TokenError as e:
            return APIResponse(
                message=f"Invalid or already revoked token: {str(e)}",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

    def _handle_registration(self, serializer, destination_label):
        if not serializer.is_valid():
            return APIResponse(
                status="error",
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return APIResponse(
            data={
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "user_type": user.user_type,
                    "phone_number": user.phone_number,
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            message=f"Registration successful. OTP has been sent to your{destination_label}.",
            status="success",
            status_code=status.HTTP_201_CREATED,
        )
