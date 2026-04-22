from django.urls import re_path
from appone import consumers

websocket_urlpatterns = [
    # ws://host/ws/workspace/<workspace_id>/
    re_path(
        r'^ws/workspace/(?P<workspace_id>[0-9a-f-]+)/$',
        consumers.WorkspaceChatConsumer.as_asgi()
    ),
]
