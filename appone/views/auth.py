from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import RegisterSerializer, LoginSerializer, LogoutSerializer


@extend_schema(tags=['Authentication'])
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Register a new user',
        description=(
            'Creates a new User account along with the corresponding '
            'FreelancerProfile or CompanyProfile. Also creates a pending '
            'OTPVerification record and triggers an SMS to the supplied '
            'phone number via Celery.'
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description='Registration successful — tokens returned.'),
            400: OpenApiResponse(description='Validation error.'),
        },
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user."""
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'message': 'Registration successful. An OTP has been sent to your phone number.',
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'user_type': user.user_type,
                    'phone_number': user.phone_number,
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'next_step': 'Verify your phone at POST /api/otp/verify_phone_otp/',
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Login',
        description='Authenticate with email and password. Returns JWT access and refresh tokens.',
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description='Login successful — tokens returned.'),
            400: OpenApiResponse(description='Invalid credentials.'),
        },
    )
    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login user and receive JWT tokens."""
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    'message': 'Login successful',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'user_type': user.user_type,
                        'is_verified': user.is_verified,
                    },
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='Logout',
        description='Blacklist the supplied refresh token, effectively logging the user out.',
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description='Logged out successfully.'),
            400: OpenApiResponse(description='Invalid or missing refresh token.'),
        },
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """Logout user by blacklisting their refresh token."""
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refresh_token = serializer.validated_data['refresh']

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'message': 'Logged out successfully.'},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except TokenError as e:
            return Response(
                {'error': f'Invalid or already revoked token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
