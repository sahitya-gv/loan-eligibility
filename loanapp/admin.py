from django.contrib import admin
from .models import LoanApplication


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_link",
        "age",
        "formatted_income",
        "formatted_loan_amount",
        "cibil_score",
        "prediction_badge",
        "probability_percent",
        "created_at",
    )
    list_filter = (
        "prediction",
        "created_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "prediction",
    )
    readonly_fields = (
        "prediction",
        "probability",
        "created_at",
    )
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    @admin.display(description="User", ordering="user__username")
    def user_link(self, obj):
        return obj.user.username

    @admin.display(description="Income")
    def formatted_income(self, obj):
        return f"${obj.income:,.2f}"

    @admin.display(description="Loan Amount")
    def formatted_loan_amount(self, obj):
        return f"${obj.loan_amount:,.2f}"

    @admin.display(description="Probability")
    def probability_percent(self, obj):
        if obj.probability is not None:
            return f"{obj.probability * 100:.1f}%"
        return "N/A"

    @admin.display(description="Status")
    def prediction_badge(self, obj):
        return obj.prediction or "Pending"
