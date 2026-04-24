from django.db import models


class CountryTaxAccount(models.Model):
    country_name = models.CharField(max_length=100, unique=True)
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20)
    paystack_subaccount_code = models.CharField(max_length=50, blank=True)
    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="e.g. 5.00 for 5%"
    )

    def __str__(self):
        return self.country_name
