from rest_framework import serializers
from appone.models import Workspace, Task, Message, ProfileAccessLog


class WorkspaceSerializer(serializers.ModelSerializer):
    """Serializer for Workspace details."""
    contract_id = serializers.ReadOnlyField(source='contract.id')

    class Meta:
        model = Workspace
        fields = '__all__'
        read_only_fields = ('id', 'contract', 'created_at', 'updated_at')


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task creation and details."""
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.__str__')
    created_by_email = serializers.ReadOnlyField(source='created_by.email')

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'created_by', 'created_at', 'updated_at')


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message creation and details."""
    sender_email = serializers.ReadOnlyField(source='sender.email')

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = (
            'id', 'workspace', 'sender', 'flagged', 'flag_reason', 'created_at'
        )


class ProfileAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for Profile Access Log details."""
    company_name = serializers.ReadOnlyField(source='company.company_name')
    freelancer_name = serializers.ReadOnlyField(source='freelancer.__str__')

    class Meta:
        model = ProfileAccessLog
        fields = '__all__'
        read_only_fields = ('id', 'accessed_at', 'otp_verified')


class UpdateTaskStatusSerializer(serializers.Serializer):
    """Serializer for updating task status."""
    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES, required=True)
