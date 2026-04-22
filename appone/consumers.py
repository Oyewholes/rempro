import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import Message, Workspace

User = get_user_model()

# Keywords that trigger automatic message flagging
_FLAGGED_KEYWORDS = ['email', 'phone', 'whatsapp', 'telegram', 'skype', '@', '+']


class WorkspaceChatConsumer(AsyncWebsocketConsumer):
    """
    Real-time WebSocket consumer for workspace-scoped messaging.

    Connection URL:
        ws://host/ws/workspace/<workspace_id>/?token=<JWT>

    The JWT is passed as a query-string parameter because the browser
    WebSocket API does not support custom headers.

    On connect:
        1. Decode & validate the JWT -> resolve the User.
        2. Confirm the workspace exists.
        3. Confirm the user is a participant (freelancer or company on the contract).
        4. Join the channel group  ``workspace_<workspace_id>``.

    On receive (text frame):
        - Expects JSON: ``{"content": "Hello!"}``
        - Saves a ``Message`` record to the database.
        - Applies the same personal-information flagging logic as the REST view.
        - Broadcasts the saved message to all members of the channel group.

    On disconnect:
        - Leaves the channel group.
    """

    # --- Connection lifecycle ---

    async def connect(self):
        # 1. Authenticate via ?token= query parameter
        token_str = self._extract_token()
        self.user = await self._authenticate(token_str)
        if self.user is None:
            # 4001 -> authentication failed
            await self.close(code=4001)
            return

        # 2. Resolve workspace
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.workspace = await self._get_workspace(self.workspace_id)
        if self.workspace is None:
            # 4004 -> workspace not found
            await self.close(code=4004)
            return

        # 3. Verify this user is a participant of the workspace contract
        if not await self._is_participant():
            # 4003 -> access forbidden
            await self.close(code=4003)
            return

        # 4. Join the channel group and accept the connection
        self.room_group_name = f'workspace_{self.workspace_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # --- Message handling ---

    async def receive(self, text_data):
        """Handle an incoming WebSocket frame from the client."""
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self.send(text_data=json.dumps({'error': 'Invalid JSON payload.'}))
            return

        content = data.get('content', '').strip()
        if not content:
            await self.send(text_data=json.dumps({'error': 'Message content cannot be empty.'}))
            return

        # Persist the message and apply flagging logic
        message = await self._save_message(content)

        # Broadcast to every client in the same workspace group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',           # routes to chat_message() handler below
                'message_id': str(message.id),
                'sender_id': str(self.user.id),
                'sender_email': self.user.email,
                'content': message.content,
                'flagged': message.flagged,
                'flag_reason': message.flag_reason,
                'created_at': message.created_at.isoformat(),
                'workspace_id': str(self.workspace_id),
            }
        )

    async def chat_message(self, event):
        """Handler called by channel layer when a group_send arrives."""
        # Forward the event payload (minus the internal 'type' key) to the WebSocket client
        payload = {k: v for k, v in event.items() if k != 'type'}
        await self.send(text_data=json.dumps(payload))

    # --- Database helpers (run in a thread pool via database_sync_to_async) ---

    def _extract_token(self) -> str | None:
        """Parse the JWT from the ``?token=`` query-string parameter."""
        raw_qs = self.scope.get('query_string', b'').decode('utf-8')
        params = {}
        for part in raw_qs.split('&'):
            if '=' in part:
                key, _, value = part.partition('=')
                params[key] = value
        return params.get('token')

    @database_sync_to_async
    def _authenticate(self, token_str: str | None):
        """Validate the JWT and return the corresponding User, or None on failure."""
        if not token_str:
            return None
        try:
            payload = AccessToken(token_str)
            return User.objects.get(id=payload['user_id'])
        except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
            return None

    @database_sync_to_async
    def _get_workspace(self, workspace_id: str):
        """Return the Workspace with the given id, or None if it doesn't exist."""
        try:
            return (
                Workspace.objects
                .select_related('contract__freelancer__user', 'contract__company__user')
                .get(id=workspace_id)
            )
        except (Workspace.DoesNotExist, Exception):
            return None

    @database_sync_to_async
    def _is_participant(self) -> bool:
        """
        Return True if self.user is either:
          - the freelancer on the workspace's contract, or
          - the company owner on the workspace's contract.
        """
        contract = self.workspace.contract
        is_freelancer = (
            hasattr(self.user, 'freelancer_profile')
            and contract.freelancer == self.user.freelancer_profile
        )
        is_company = (
            hasattr(self.user, 'company_profile')
            and contract.company == self.user.company_profile
        )
        return is_freelancer or is_company

    @database_sync_to_async
    def _save_message(self, content: str) -> Message:
        """
        Persist a Message to the database.
        Applies the same personal-information flagging logic as the REST MessageViewSet.
        """
        content_lower = content.lower()
        flagged = any(keyword in content_lower for keyword in _FLAGGED_KEYWORDS)

        return Message.objects.create(
            workspace=self.workspace,
            sender=self.user,
            content=content,
            flagged=flagged,
            flag_reason='Possible personal information exchange detected' if flagged else '',
        )
