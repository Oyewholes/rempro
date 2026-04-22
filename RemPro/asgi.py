"""
ASGI config for RemPro project.

Supports both HTTP (Django) and WebSocket (Django Channels) protocols.
Run with Daphne:  daphne RemPro.asgi:application
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RemPro.settings")

# Initialize Django ASGI application early to ensure the app registry is ready
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from appone.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # All standard HTTP requests go through Django as usual
    "http": django_asgi_app,

    # WebSocket requests are routed through Channels
    # AllowedHostsOriginValidator enforces ALLOWED_HOSTS for WS connections
    "websocket": AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
