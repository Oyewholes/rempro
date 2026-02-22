from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from appone.serializers import TaskSerializer
from appone.models import Task
from django.utils import timezone



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

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update task status"""
        task = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Task.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
        task.save()

        return Response({
            'message': 'Task status updated',
            'task': TaskSerializer(task).data
        }, status=status.HTTP_200_OK)

