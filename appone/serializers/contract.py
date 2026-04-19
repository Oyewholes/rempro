from rest_framework import serializers
from appone.models import Contract, Payment
from .job import JobApplicationSerializer


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract creation and details."""
    job_title = serializers.ReadOnlyField(source='job_application.job.title')
    freelancer_name = serializers.ReadOnlyField(source='freelancer.__str__')
    company_name = serializers.ReadOnlyField(source='company.company_name')

    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ('id', 'company', 'freelancer', 'status', 'created_at', 'updated_at')


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment details."""
    contract_details = ContractSerializer(source='contract', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = (
            'id', 'contract', 'platform_tax', 'dwelling_country_tax',
            'work_country_tax', 'net_amount', 'status', 'payment_date',
            'processed_at', 'transaction_reference',
        )
