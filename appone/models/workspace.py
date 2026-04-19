from django.db import models
import uuid


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.OneToOneField(
        'appone.Contract', on_delete=models.CASCADE, related_name='workspace'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Workspace: {self.name}"


class Task(models.Model):
    STATUS_CHOICES = (
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='tasks'
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, default='medium')

    assigned_to = models.ForeignKey(
        'appone.FreelancerProfile',
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
    )
    created_by = models.ForeignKey(
        'appone.User', on_delete=models.CASCADE, related_name='created_tasks'
    )

    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.workspace.name}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        'appone.User', on_delete=models.CASCADE, related_name='sent_messages'
    )

    content = models.TextField()
    flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.email} in {self.workspace.name}"


class ProfileAccessLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'appone.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='access_logs',
    )
    freelancer = models.ForeignKey(
        'appone.FreelancerProfile',
        on_delete=models.CASCADE,
        related_name='profile_access_logs',
    )

    accessed_at = models.DateTimeField(auto_now_add=True)
    otp_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company.company_name} accessed {self.freelancer}"
