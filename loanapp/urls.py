from django.urls import path
from .views import (
    current_user,
    create_loan,
    estimate_eligibility,
    get_loan_detail,
    get_loans,
    health_check,
    login_view,
    logout_view,
    register,
)

urlpatterns = [
    # System health endpoint
    path("health/", health_check, name="health-check"),

    # Auth endpoints
    path("register/", register, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("me/", current_user, name="current-user"),

    # Loan endpoints
    path("loans/", create_loan, name="create-loan"),
    path("loans/list/", get_loans, name="loan-list"),
    path("loans/<int:pk>/", get_loan_detail, name="loan-detail"),
    path("predict/", estimate_eligibility, name="estimate-eligibility"),
]

