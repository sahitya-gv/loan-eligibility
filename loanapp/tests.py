from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .ml_service import LoanEligibilityPredictor, predictor
from .models import LoanApplication


class AuthenticationTests(TestCase):
    """Automated test cases for User Registration, Login, Profile and Logout."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.logout_url = reverse("logout")
        self.me_url = reverse("current-user")
        self.valid_user_data = {
            "username": "johndoe",
            "email": "johndoe@example.com",
            "password": "SecurePassword123!",
        }

    def test_user_registration_success(self):
        """Test successful registration with valid credentials."""
        response = self.client.post(self.register_url, self.valid_user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "johndoe")
        self.assertEqual(response.data["user"]["email"], "johndoe@example.com")
        self.assertTrue(User.objects.filter(username="johndoe").exists())

    def test_user_registration_duplicate_username(self):
        """Test registration rejection when username already exists."""
        User.objects.create_user(
            username="johndoe",
            email="existing@example.com",
            password="SomePassword123!"
        )
        response = self.client.post(self.register_url, self.valid_user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("username", response.data["errors"])

    def test_user_registration_duplicate_email(self):
        """Test registration rejection when email already exists."""
        User.objects.create_user(
            username="differentuser",
            email="johndoe@example.com",
            password="SomePassword123!"
        )
        response = self.client.post(self.register_url, self.valid_user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("email", response.data["errors"])

    def test_user_registration_missing_fields(self):
        """Test registration rejection when required fields are missing."""
        response = self.client.post(self.register_url, {"username": "incomplete"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_user_login_success_with_username(self):
        """Test successful login using username and password."""
        User.objects.create_user(
            username="johndoe",
            email="johndoe@example.com",
            password="SecurePassword123!"
        )
        response = self.client.post(
            self.login_url,
            {"username": "johndoe", "password": "SecurePassword123!"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("token", response.data)

    def test_user_login_success_with_email(self):
        """Test successful login using email address as identifier."""
        User.objects.create_user(
            username="johndoe",
            email="johndoe@example.com",
            password="SecurePassword123!"
        )
        response = self.client.post(
            self.login_url,
            {"username": "johndoe@example.com", "password": "SecurePassword123!"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_user_login_invalid_password(self):
        """Test rejection when invalid password is provided."""
        User.objects.create_user(
            username="johndoe",
            email="johndoe@example.com",
            password="SecurePassword123!"
        )
        response = self.client.post(
            self.login_url,
            {"username": "johndoe", "password": "WrongPassword!"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_user_login_nonexistent_user(self):
        """Test rejection for nonexistent username."""
        response = self.client.post(
            self.login_url,
            {"username": "ghostuser", "password": "AnyPassword123!"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_logout_and_token_revocation(self):
        """Test that logout successfully revokes authorization."""
        user = User.objects.create_user(
            username="johndoe",
            email="johndoe@example.com",
            password="SecurePassword123!"
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])


class LoanValidationAndCreationTests(TestCase):
    """Automated tests for Loan Application input validation, constraints, and creation."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="borrower1",
            email="borrower1@example.com",
            password="Password123!"
        )
        self.client.force_authenticate(user=self.user)
        self.create_loan_url = reverse("create-loan")
        self.valid_payload = {
            "age": 30,
            "income": "75000.00",
            "loan_amount": "200000.00",
            "cibil_score": 780,
        }

    def test_create_loan_successful(self):
        """Test successful loan application creation and automatic ML prediction."""
        response = self.client.post(self.create_loan_url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["loan"]["username"], self.user.username)
        self.assertEqual(response.data["loan"]["age"], 30)
        self.assertIn(response.data["prediction_details"]["prediction"], ["Eligible", "Not Eligible"])
        self.assertIsNotNone(response.data["prediction_details"]["probability"])
        self.assertIn("disclaimer", response.data["prediction_details"])

        # Verify database record
        loan = LoanApplication.objects.get(id=response.data["loan"]["id"])
        self.assertEqual(loan.user, self.user)
        self.assertEqual(loan.cibil_score, 780)

    def test_prevent_user_spoofing(self):
        """Ensure malicious user cannot submit loan under another user's name via JSON body."""
        other_user = User.objects.create_user(
            username="victim_user",
            email="victim@example.com",
            password="Password123!"
        )
        payload = self.valid_payload.copy()
        payload["username"] = "victim_user"
        payload["user_id"] = other_user.id

        response = self.client.post(self.create_loan_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan_id = response.data["loan"]["id"]
        loan = LoanApplication.objects.get(id=loan_id)
        # Must be bound to authenticated user, NOT victim_user
        self.assertEqual(loan.user, self.user)
        self.assertNotEqual(loan.user, other_user)

    def test_age_boundary_under_18_rejected(self):
        """Test rejection when applicant age is under 18."""
        payload = self.valid_payload.copy()
        payload["age"] = 17
        response = self.client.post(self.create_loan_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("age", response.data["errors"])

    def test_age_boundary_over_100_rejected(self):
        """Test rejection when applicant age is over 100."""
        payload = self.valid_payload.copy()
        payload["age"] = 101
        response = self.client.post(self.create_loan_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("age", response.data["errors"])

    def test_age_boundaries_accepted(self):
        """Test valid boundary ages 18 and 100."""
        for valid_age in [18, 100]:
            payload = self.valid_payload.copy()
            payload["age"] = valid_age
            response = self.client.post(self.create_loan_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_negative_or_zero_income_rejected(self):
        """Test rejection for non-positive income."""
        for invalid_income in ["0.00", "-5000.00"]:
            payload = self.valid_payload.copy()
            payload["income"] = invalid_income
            response = self.client.post(self.create_loan_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("income", response.data["errors"])

    def test_negative_or_zero_loan_amount_rejected(self):
        """Test rejection for non-positive loan amount."""
        for invalid_amount in ["0.00", "-10000.00"]:
            payload = self.valid_payload.copy()
            payload["loan_amount"] = invalid_amount
            response = self.client.post(self.create_loan_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("loan_amount", response.data["errors"])

    def test_cibil_score_out_of_range_rejected(self):
        """Test rejection for CIBIL scores outside 300 to 900."""
        for invalid_cibil in [299, 901, -1, 1000]:
            payload = self.valid_payload.copy()
            payload["cibil_score"] = invalid_cibil
            response = self.client.post(self.create_loan_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("cibil_score", response.data["errors"])


class AuthorizationAndDataIsolationTests(TestCase):
    """Automated tests for Role-Based Access Control and Cross-User Data Isolation."""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="user_a", email="a@example.com", password="Password123!"
        )
        self.user_b = User.objects.create_user(
            username="user_b", email="b@example.com", password="Password123!"
        )
        self.admin_user = User.objects.create_superuser(
            username="admin_user", email="admin@example.com", password="Password123!"
        )

        # Create loans for User A and User B
        self.loan_a = LoanApplication.objects.create(
            user=self.user_a,
            age=32,
            income=Decimal("80000.00"),
            loan_amount=Decimal("150000.00"),
            cibil_score=760,
            prediction="Eligible",
            probability=0.88,
        )
        self.loan_b = LoanApplication.objects.create(
            user=self.user_b,
            age=45,
            income=Decimal("50000.00"),
            loan_amount=Decimal("300000.00"),
            cibil_score=620,
            prediction="Not Eligible",
            probability=0.35,
        )

    def test_unauthenticated_requests_rejected(self):
        """Ensure anonymous requests to protected endpoints return 401 Unauthorized."""
        self.client.logout()
        res1 = self.client.get(reverse("loan-list"))
        self.assertEqual(res1.status_code, status.HTTP_401_UNAUTHORIZED)

        res2 = self.client.post(reverse("create-loan"), {})
        self.assertEqual(res2.status_code, status.HTTP_401_UNAUTHORIZED)

        res3 = self.client.get(reverse("loan-detail", kwargs={"pk": self.loan_a.id}))
        self.assertEqual(res3.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_only_sees_own_loans_in_list(self):
        """Verify regular user can only see their own applications in list endpoint."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(reverse("loan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["loans"][0]["id"], self.loan_a.id)

    def test_user_cannot_access_other_users_loan_detail(self):
        """Verify User A receives 403 Forbidden when accessing User B's loan detail."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(reverse("loan-detail", kwargs={"pk": self.loan_b.id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["success"])

    def test_staff_admin_can_view_all_loans(self):
        """Verify staff/admin user can view all loans across all users."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("loan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class MLPredictionModuleTests(TestCase):
    """Automated tests for ML Prediction Service logic, probability calibration, and fallbacks."""

    def setUp(self):
        self.predictor = LoanEligibilityPredictor()

    def test_high_credit_profile_prediction(self):
        """Prime borrower should be predicted as Eligible with high probability."""
        result = self.predictor.predict(
            age=35,
            income=120000.0,
            loan_amount=200000.0,
            cibil_score=820,
        )
        self.assertEqual(result["prediction"], "Eligible")
        self.assertGreaterEqual(result["probability"], 0.70)
        self.assertIn("disclaimer", result)
        self.assertIsInstance(result["risk_factors"], list)

    def test_low_credit_profile_prediction(self):
        """Subprime borrower with low CIBIL should be predicted as Not Eligible."""
        result = self.predictor.predict(
            age=22,
            income=20000.0,
            loan_amount=300000.0,
            cibil_score=520,
        )
        self.assertEqual(result["prediction"], "Not Eligible")
        self.assertLess(result["probability"], 0.50)
        self.assertTrue(len(result["risk_factors"]) > 0)

    def test_feature_validation_ranges(self):
        """Test feature validation raises ValueError on out-of-range inputs."""
        with self.assertRaises(ValueError):
            self.predictor.validate_features(age=15, income=50000, loan_amount=100000, cibil_score=750)
        with self.assertRaises(ValueError):
            self.predictor.validate_features(age=30, income=-100, loan_amount=100000, cibil_score=750)
        with self.assertRaises(ValueError):
            self.predictor.validate_features(age=30, income=50000, loan_amount=-500, cibil_score=750)
        with self.assertRaises(ValueError):
            self.predictor.validate_features(age=30, income=50000, loan_amount=100000, cibil_score=150)


class EndToEndWorkflowTests(TestCase):
    """Full end-to-end integration test of the user journey."""

    def setUp(self):
        self.client = APIClient()

    def test_complete_user_journey(self):
        # 1. User Registration
        reg_response = self.client.post(
            reverse("register"),
            {
                "username": "alicewalton",
                "email": "alice@example.com",
                "password": "SuperSecretPassword99!",
            },
            format="json"
        )
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)
        token = reg_response.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        # 2. Check Profile
        me_response = self.client.get(reverse("current-user"))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["user"]["username"], "alicewalton")

        # 3. Interactive Pre-qualification estimation
        est_response = self.client.post(
            reverse("estimate-eligibility"),
            {"age": 28, "income": 65000, "loan_amount": 120000, "cibil_score": 740},
            format="json"
        )
        self.assertEqual(est_response.status_code, status.HTTP_200_OK)
        self.assertEqual(est_response.data["estimate"]["prediction"], "Eligible")

        # 4. Submit Formal Loan Application
        loan_response = self.client.post(
            reverse("create-loan"),
            {"age": 28, "income": "65000.00", "loan_amount": "120000.00", "cibil_score": 740},
            format="json"
        )
        self.assertEqual(loan_response.status_code, status.HTTP_201_CREATED)
        loan_id = loan_response.data["loan"]["id"]

        # 5. Fetch User's Loan Applications
        list_response = self.client.get(reverse("loan-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)

        # 6. Retrieve Specific Loan Details
        detail_response = self.client.get(reverse("loan-detail", kwargs={"pk": loan_id}))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["loan"]["id"], loan_id)

        # 7. Logout
        logout_response = self.client.post(reverse("logout"))
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)


class HealthCheckTests(TestCase):
    """Automated tests for public container and system health monitoring probes."""

    def setUp(self):
        self.client = APIClient()

    def test_health_check_api_endpoint_success(self):
        """GET /api/health/ should return 200 OK and healthy status."""
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["database"], "healthy")
        self.assertEqual(response.data["service"], "loan-eligibility-api")
        self.assertIn("ml_engine", response.data)

    def test_health_check_healthz_endpoint_success(self):
        """GET /healthz/ root route should also return 200 OK."""
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")

    @patch("loanapp.views.connection.cursor")
    def test_health_check_database_failure(self, mock_cursor):
        """When database fails, health check must return 503 Service Unavailable."""
        mock_cursor.side_effect = Exception("DB Connection refused")
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["database"], "disconnected")


class NegativeAndEdgeCaseIntegrationTests(TestCase):
    """Negative tests: malformed input, method not allowed, unauthenticated calls, boundary types."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testneguser",
            email="neg@example.com",
            password="StrongPassword123!"
        )

    def test_register_invalid_http_methods(self):
        """GET or PUT to /api/register/ should return 405 Method Not Allowed."""
        res_get = self.client.get(reverse("register"))
        self.assertEqual(res_get.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        res_put = self.client.put(reverse("register"), {})
        self.assertEqual(res_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_loan_create_invalid_http_methods(self):
        """GET or DELETE to /api/loans/ should return 405 Method Not Allowed."""
        self.client.force_authenticate(user=self.user)
        res_get = self.client.get(reverse("create-loan"))
        self.assertEqual(res_get.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_loan_create_malformed_non_numeric_fields(self):
        """Submitting non-numeric strings for numeric fields returns 400 Bad Request."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "age": "thirty",
            "income": "not-a-number",
            "loan_amount": "fifty-thousand",
            "cibil_score": "excellent"
        }
        response = self.client.post(reverse("create-loan"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("errors", response.data)

    def test_estimate_eligibility_unauthenticated(self):
        """Unauthenticated call to /api/predict/ must return 401."""
        response = self.client.post(reverse("estimate-eligibility"), {"age": 30, "income": 50000})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_estimate_eligibility_invalid_types(self):
        """Invalid types passed to /api/predict/ should return 400 Bad Request."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("estimate-eligibility"),
            {"age": "invalid", "income": "abc", "loan_amount": "xyz", "cibil_score": "good"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_estimate_eligibility_out_of_range_cibil(self):
        """CIBIL score out of range returns 400 with validation message."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("estimate-eligibility"),
            {"age": 30, "income": 50000, "loan_amount": 100000, "cibil_score": 100},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])


