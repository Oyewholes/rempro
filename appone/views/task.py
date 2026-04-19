from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from appone.serializers import TaskSerializer, UpdateTaskStatusSerializer
from appone.models import Task
from django.utils import timezone


@extend_schema(tags=['Tasks'])
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Task.objects.filter(assigned_to=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Task.objects.filter(workspace__contract__company=self.request.user.company_profile)
        return Task.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(
        summary='Update task status',
        description='Update the status of a task (e.g. todo, in_progress, completed).',
        request=UpdateTaskStatusSerializer,
        responses={
            200: OpenApiResponse(description='Task status updated.'),
            400: OpenApiResponse(description='Invalid status.'),
        },
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update task status"""
        task = self.get_object()
        serializer = UpdateTaskStatusSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']

        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
        task.save()

        return Response({
            'message': 'Task status updated',
            'task': TaskSerializer(task).data
        }, status=status.HTTP_200_OK)
