from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import Task
from appone.serializers import TaskSerializer, UpdateTaskStatusSerializer
from appone.utils import APIResponse


@extend_schema(tags=["Tasks"])
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "freelancer_profile"):
            return Task.objects.filter(assigned_to=user.freelancer_profile)
        elif hasattr(user, "company_profile"):
            return Task.objects.filter(
                workspace__contract__company=user.company_profile
            )
        return Task.objects.none()

    def perform_create(self, serializer):
        workspace = serializer.validated_data["workspace"]
        user = self.request.user
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
        assigned_to = serializer.validated_data.get("assigned_to")
        if assigned_to and workspace.contract.freelancer != assigned_to:
            raise serializers.ValidationError(
                "You can only assign tasks to freelancers in your workspace."
            )
        serializer.save(created_by=user)

    @extend_schema(
        summary="Update task status",
        description="Update the status of a task (e.g. todo, in_progress, completed).",
        request=UpdateTaskStatusSerializer,
        responses={
            200: OpenApiResponse(description="Task status updated."),
            400: OpenApiResponse(description="Invalid status."),
        },
    )
    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update task status"""
        task = self.get_object()
        serializer = UpdateTaskStatusSerializer(data=request.data)

        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        new_status = serializer.validated_data["status"]
        if new_status == "completed":
            if (
                not hasattr(request.user, "company_profile")
                or task.workspace.contract.company != request.user.company_profile
            ):
                return APIResponse(
                    message="Only the company can mark a task as completed.",
                    status_code=status.HTTP_403_FORBIDDEN,
                    status="error",
                )
            task.completed_at = timezone.now()

        task.status = new_status
        task.save()

        return APIResponse(
            data={"task": TaskSerializer(task).data},
            message="Task status updated",
            status_code=status.HTTP_200_OK,
            status="success",
        )
