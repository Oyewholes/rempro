from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import Message
from appone.serializers import MessageSerializer
from appone.utils import APIResponse


@extend_schema(tags=["Messages"])
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "freelancer_profile"):
            return Message.objects.filter(
                workspace__contract__freelancer=self.request.user.freelancer_profile
            )
        elif hasattr(self.request.user, "company_profile"):
            return Message.objects.filter(
                workspace__contract__company=self.request.user.company_profile
            )
        return Message.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        workspace = serializer.validated_data["workspace"]
        if (
            hasattr(user, "company_profile")
            and workspace.contract.company != user.company_profile
        ):
            raise serializers.ValidationError(
                "You do not have access to this workspace."
            )
        elif (
            hasattr(user, "freelancer_profile")
            and workspace.contract.freelancer != user.freelancer_profile
        ):
            raise serializers.ValidationError(
                "You do not have access to this workspace."
            )
        message = serializer.save(sender=user)

        flagged_keywords = ["email", "phone", "whatsapp", "telegram", "skype", "@", "+"]
        content_lower = message.content.lower()

        if any(keyword in content_lower for keyword in flagged_keywords):
            message.flagged = True
            message.flag_reason = "Possible personal information exchange detected"
            message.save()

    @extend_schema(
        summary="Get workspace messages",
        description="Retrieve all messages for a specific workspace.",
        parameters=[
            OpenApiParameter(
                "workspace_id", str, description="Workspace UUID", required=True
            )
        ],
        responses={
            200: MessageSerializer(many=True),
            400: OpenApiResponse(description="workspace_id is required."),
        },
    )
    @action(detail=False, methods=["get"])
    def workspace_messages(self, request):
        """Get messages for a specific workspace"""
        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            return APIResponse(
                message="workspace_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        messages = (
            self.get_queryset().filter(workspace_id=workspace_id).order_by("created_at")
        )
        return APIResponse(
            data=MessageSerializer(messages, many=True).data,
            message="Messages retrieved successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )
