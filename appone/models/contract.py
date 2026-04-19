from decimal import Decimal
from django.db import models
import uuid


class Contract(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application = models.OneToOneField(
        'appone.JobApplication', on_delete=models.CASCADE, related_name='contract'
    )
    company = models.ForeignKey(
        'appone.CompanyProfile', on_delete=models.CASCADE, related_name='contracts'
    )
    freelancer = models.ForeignKey(
        'appone.FreelancerProfile', on_delete=models.CASCADE, related_name='contracts'
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Tax Information
    platform_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00')
    )
    dwelling_country_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00')
    )
    work_country_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Contract: {self.freelancer} - {self.company.company_name}"


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='payments'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    # Tax Breakdown
    platform_tax = models.DecimalField(max_digits=10, decimal_places=2)
    dwelling_country_tax = models.DecimalField(max_digits=10, decimal_places=2)
    work_country_tax = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    payment_date = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    payment_method = models.CharField(max_length=50)
    transaction_reference = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"Payment: {self.contract} - {self.amount} {self.currency}"
