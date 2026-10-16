import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import connection
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .ml_service import predictor
from .models import LoanApplication
from .serializers import (
    LoanApplicationSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


# ==============================
# 1. AUTHENTICATION VIEWS
# ==============================

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """
    User registration endpoint.
    Validates unique username, email format, password complexity, and issues an auth token.
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "success": False,
                "message": "Registration validation failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)

    logger.info("New user registered: %s (ID: %d)", user.username, user.id)

    return Response(
        {
            "success": True,
            "message": "Registration successful.",
            "token": token.key,
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    User authentication endpoint.
    Verifies credentials, logs in session, and returns an auth token.
    """
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response(
            {
                "success": False,
                "message": "Both username and password are required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Support login with username or email
    user = authenticate(request, username=username, password=password)
    if user is None and "@" in username:
        try:
            user_obj = User.objects.get(email__iexact=username)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

    if user is None:
        return Response(
            {
                "success": False,
                "message": "Invalid credentials provided.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {
                "success": False,
                "message": "User account is inactive or disabled.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Establish session & issue token
    login(request, user)
    token, _ = Token.objects.get_or_create(user=user)

    logger.info("User logged in successfully: %s", user.username)

    return Response(
        {
            "success": True,
            "message": "Login successful.",
            "token": token.key,
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint.
    Revokes the auth token and flushes session data.
    """
    try:
        if hasattr(request.user, "auth_token") and request.user.auth_token:
            request.user.auth_token.delete()
    except Exception as e:
        logger.warning("Error deleting auth token on logout: %s", e)

    logout(request)
    return Response(
        {
            "success": True,
            "message": "Logged out successfully.",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user(request):
    """
    Returns profile information of the currently authenticated user.
    """
    return Response(
        {
            "success": True,
            "user": UserSerializer(request.user).data,
        },
        status=status.HTTP_200_OK,
    )


# ==============================
# 2. LOAN APPLICATION & ML VIEWS
# ==============================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_loan(request):
    """
    Creates a new loan application for the authenticated user and runs ML eligibility inference.
    Prevents user identity spoofing by binding directly to request.user.
    """
    serializer = LoanApplicationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "success": False,
                "message": "Invalid loan application data.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated_data = serializer.validated_data

    # Execute ML eligibility prediction
    try:
        prediction_result = predictor.predict(
            age=validated_data["age"],
            income=validated_data["income"],
            loan_amount=validated_data["loan_amount"],
            cibil_score=validated_data["cibil_score"],
        )
    except Exception as e:
        logger.error("ML prediction error for user %s: %s", request.user.username, e)
        return Response(
            {
                "success": False,
                "message": "An error occurred during loan eligibility estimation. Please try again.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Persist loan application with user association and prediction
    loan = serializer.save(
        user=request.user,
        prediction=prediction_result["prediction"],
        probability=prediction_result["probability"],
    )

    logger.info(
        "Loan application #%d created for user %s. Result: %s (Prob: %.2f)",
        loan.id,
        request.user.username,
        loan.prediction,
        loan.probability or 0.0,
    )

    return Response(
        {
            "success": True,
            "message": "Loan application submitted and evaluated successfully.",
            "loan": LoanApplicationSerializer(loan).data,
            "prediction_details": {
                "prediction": loan.prediction,
                "probability": loan.probability,
                "disclaimer": prediction_result.get("disclaimer"),
                "risk_factors": prediction_result.get("risk_factors", []),
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_loans(request):
    """
    Retrieves loan applications with strict access control:
    - Regular users: Only their own applications.
    - Staff / Admins: All applications or filtered by ?username= / ?user_id=.
    """
    if request.user.is_staff:
        queryset = LoanApplication.objects.select_related("user").all()
        username_filter = request.query_params.get("username")
        user_id_filter = request.query_params.get("user_id")

        if username_filter:
            queryset = queryset.filter(user__username__iexact=username_filter)
        if user_id_filter:
            queryset = queryset.filter(user__id=user_id_filter)
    else:
        queryset = LoanApplication.objects.select_related("user").filter(user=request.user)

    serializer = LoanApplicationSerializer(queryset, many=True)

    return Response(
        {
            "success": True,
            "count": queryset.count(),
            "loans": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_loan_detail(request, pk):
    """
    Retrieves a single loan application by ID.
    Enforces authorization check: users cannot access applications belonging to other users.
    """
    try:
        loan = LoanApplication.objects.select_related("user").get(pk=pk)
    except LoanApplication.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Loan application not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Authorization enforcement
    if loan.user != request.user and not request.user.is_staff:
        return Response(
            {
                "success": False,
                "message": "You do not have permission to view this loan application.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            "success": True,
            "loan": LoanApplicationSerializer(loan).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def estimate_eligibility(request):
    """
    Quick ML estimation endpoint without creating a saved loan record.
    Useful for interactive pre-qualification checks.
    """
    try:
        age = int(request.data.get("age", 0))
        income = float(request.data.get("income", 0))
        loan_amount = float(request.data.get("loan_amount", 0))
        cibil_score = int(request.data.get("cibil_score", 0))
    except (ValueError, TypeError):
        return Response(
            {
                "success": False,
                "message": "Invalid numeric input provided for estimation.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = predictor.predict(
            age=age,
            income=income,
            loan_amount=loan_amount,
            cibil_score=cibil_score,
        )
    except ValueError as e:
        return Response(
            {
                "success": False,
                "message": str(e),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error("Error during standalone prediction: %s", e)
        return Response(
            {
                "success": False,
                "message": "Prediction failed due to an internal error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "success": True,
            "estimate": result,
        },
        status=status.HTTP_200_OK,
    )


# ==============================
# 3. SYSTEM HEALTH CHECK
# ==============================

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Public health check endpoint for monitoring, Docker, and Render service readiness.
    Verifies that the application can query the database and reports ML engine status.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_status = "healthy"
    except Exception as exc:
        logger.error("Health check database probe failed: %s", exc)
        return Response(
            {
                "status": "unhealthy",
                "database": "disconnected",
                "service": "loan-eligibility-api",
                "error": "Database connectivity failed.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "status": "healthy",
            "database": db_status,
            "service": "loan-eligibility-api",
            "ml_engine": "loaded_artifact" if predictor._is_model_loaded else "calibrated_scoring_engine",
        },
        status=status.HTTP_200_OK,
    )

