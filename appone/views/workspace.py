from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from appone.models import Workspace
from appone.serializers import WorkspaceSerializer


@extend_schema(tags=["Workspaces"])
class WorkspaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, "freelancer_profile"):
            return Workspace.objects.filter(
                contract__freelancer=self.request.user.freelancer_profile
            )
        elif hasattr(self.request.user, "company_profile"):
            return Workspace.objects.filter(
                contract__company=self.request.user.company_profile
            )
        return Workspace.objects.none()
