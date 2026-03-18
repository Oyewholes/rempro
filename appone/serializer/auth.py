from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import transaction
from appone.models import User, FreelancerProfile, CompanyProfile, OTPVerification
import re
from appone.utils import generate_otp
from django.utils import timezone
from datetime import timedelta
from appone.tasks import send_otp_task, send_company_email_otp_task
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError


class RegisterFreelancerSerializer(serializers.ModelSerializer):
    """
    Validates and creates a new freelancer user on registration.

    Expects:
        - email
        - password / password2  (confirmation, write-only, never returned)
        - user_type              (freelancer | admin)
        - phone_number           (used to seed the profile + kick off OTP)

    On success this creates three records atomically:
        1. User
        2. FreelancerProfile (seeded with phone_number)
        3. OTPVerification  (phone type, 10-min expiry, ready to be sent)
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label='Confirm Password',
    )

    # Accepted here at registration
    phone_number = serializers.CharField(
        required=True,
        max_length=14,
        help_text="Nigerian format: +234XXXXXXXXXX",
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'user_type', 'password', 'password2', 'phone_number')
        read_only_fields = ('id',)

    def validate_phone_number(self, value):
        if not re.match(r'^\+234\d{10}$', value):
            raise serializers.ValidationError(
                "Phone number must be in Nigerian format: +234XXXXXXXXXX"
            )
        # Check uniqueness across FreelancerProfile
        if (FreelancerProfile.objects.filter(phone_number=value).exists() or
                CompanyProfile.objects.filter(phone_number=value).exists() or
                User.objects.filter(phone_number=value).exists()):
            raise serializers.ValidationError(
                "An account with this phone number already exists."
            )
        return value

    def validate_user_type(self, value):
        if value not in ('freelancer',  'admin'):
            raise serializers.ValidationError(
                "user_type must be 'freelancer' or 'admin'."
            )
        return value


    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': "Password fields didn't match."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password2')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            user_type=validated_data['user_type'],
            phone_number=validated_data['phone_number'],
        )
        if user.user_type == 'freelancer':
            FreelancerProfile.objects.create(
                user=user,
                phone_number=user.phone_number
            )

        elif user.user_type == 'admin':
            User.objects.update(
                is_staff = True,
                is_superuser = True
            )

        otp = OTPVerification.objects.create(
            user=user,
            otp_code=generate_otp(),
            otp_type='phone',
            phone_number=user.phone_number,
            email = user.email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        try:
            send_otp_task.delay(otp.id)  # async via Celery when broker is running
        except Exception:
            send_otp_task(otp.id)

        return user


class LoginSerializer(serializers.Serializer):
    """
    Validates login credentials.
    On success, the authenticated User instance is available at validated_data['user'].
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def validate(self, data):
        user = authenticate(
            request=self.context.get('request'),
            username=data['email'],
            password=data['password'],
        )
        if not user:
            raise serializers.ValidationError(
                'Unable to log in with provided credentials.',
                code='authorization',
            )
        if not user.is_active:
            raise serializers.ValidationError(
                'User account is disabled.',
                code='authorization',
            )
        if user.user_type == 'freelancer' and not user.phone_number:
            raise serializers.ValidationError(
                'please verify your phone number before logging in.',
                code='authorization',
            )
        if user.user_type == 'company' and not user.is_verified:
            raise serializers.ValidationError(
                'please verify your email address before logging in.',
                code='authorization',
            )

        data['user'] = user
        return data


class RegisterCompanySerializer(serializers.ModelSerializer):
    """
    Validates and creates a new Company user on registration.

    Expects:
        - email
        - password / password2  (confirmation, write-only, never returned)
        - user_type              (company | admin)
        - email           (used to kick off OTP)

    On success this creates three records atomically:
        1. User
        2. CompanyProfile (seeded with phone_number)
        3. OTPVerification  (email, 10-min expiry, ready to be sent)
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label='Confirm Password',
    )


    class Meta:
        model = User
        fields = ('id', 'email', 'user_type', 'password', 'password2')
        read_only_fields = ('id',)

    def validate_email(self, value):
        try:
            django_validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "Email must be a valid email address."
            )

        # Check uniqueness across FreelancerProfile
        if (
                CompanyProfile.objects.filter(company_email=value).exists() or
                User.objects.filter(email=value).exists()):
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return value

    def validate_user_type(self, value):
        if value != 'company':
            raise serializers.ValidationError(
                "user_type must be 'company'"
            )
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': "Password fields didn't match."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password2')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            user_type='company',
        )

        CompanyProfile.objects.create(
            user=user,
            company_email=user.email,
        )

        otp = OTPVerification.objects.create(
            user=user,
            otp_code=generate_otp(),
            otp_type='Company_email',
            phone_number='',
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        try:
            send_company_email_otp_task.apply_async(
                args=[str(otp.id)],
                ignore_result=False,
            )
        except Exception:
            send_company_email_otp_task.apply_async(
                args=[str(otp.id)],
                ignore_result=False,
            )

        return user

