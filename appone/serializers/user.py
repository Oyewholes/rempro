from rest_framework import serializers
from appone.models import User


class UserInfoSerializer(serializers.ModelSerializer):
    """Helper serializer for User's public details."""

    class Meta:
        model = User
        fields = ('id', 'email', 'user_type', 'is_verified')
        read_only_fields = fields
