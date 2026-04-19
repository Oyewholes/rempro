from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from appone.serializers import MessageSerializer
from appone.models import Message


@extend_schema(tags=['Messages'])
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'freelancer_profile'):
            return Message.objects.filter(workspace__contract__freelancer=self.request.user.freelancer_profile)
        elif hasattr(self.request.user, 'company_profile'):
            return Message.objects.filter(workspace__contract__company=self.request.user.company_profile)
        return Message.objects.none()

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)

        # Check for personal information in message
        flagged_keywords = ['email', 'phone', 'whatsapp', 'telegram', 'skype', '@', '+']
        content_lower = message.content.lower()

        if any(keyword in content_lower for keyword in flagged_keywords):
            message.flagged = True
            message.flag_reason = 'Possible personal information exchange detected'
            message.save()

    @extend_schema(
        summary='Get workspace messages',
        description='Retrieve all messages for a specific workspace.',
        parameters=[
            OpenApiParameter('workspace_id', str, description='Workspace UUID', required=True)
        ],
        responses={
            200: MessageSerializer(many=True),
            400: OpenApiResponse(description='workspace_id is required.'),
        },
    )
    @action(detail=False, methods=['get'])
    def workspace_messages(self, request):
        """Get messages for a specific workspace"""
        workspace_id = request.query_params.get('workspace_id')
        if not workspace_id:
            return Response({'error': 'workspace_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        messages = self.get_queryset().filter(workspace_id=workspace_id).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
