from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from appone.models import OTPVerification
from appone.serializers import UserRegistrationSerializer, UserLoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from appone.schemas import RegisterRequestSchema, LoginRequestSchema
from appone.tasks import send_otp_task


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """
                Register a new user.

                Required body:
                    email, password, password2, user_type, phone_number

                On success:
                    - Creates User
                    - Creates FreelancerProfile or CompanyProfile (seeded with phone_number)
                    - Creates a pending OTPVerification record (phone type)
                      → call POST /api/otp/send_phone_otp/ next to trigger the SMS
                """
        serializer = RegisterRequestSchema(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
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
        }, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login user"""
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'user_type': user.user_type,
                    'is_verified': user.is_verified
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """Logout user by blacklisting their refresh token."""
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token= RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'message': 'Logged out successfully.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except TokenError as e:
            return Response(
                {'error': f'Invalid or already revoked token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
