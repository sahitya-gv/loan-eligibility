from django.db import models
from django.contrib.auth.models import User


class LoanApplication(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="loan_applications"
    )

    age = models.IntegerField()
    income = models.DecimalField(max_digits=12, decimal_places=2)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    cibil_score = models.IntegerField()

    prediction = models.CharField(max_length=20, blank=True)
    probability = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Loan Application"
        verbose_name_plural = "Loan Applications"

    def __str__(self):
        return f"{self.user.username} - {self.loan_amount} ({self.prediction or 'Pending'})"
