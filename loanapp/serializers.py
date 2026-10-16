import re
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import LoanApplication


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_username(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if not re.match(r"^[\w.@+-]+$", value):
            raise serializers.ValidationError("Username contains invalid characters.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_password(self, value):
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user


class LoanApplicationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = LoanApplication
        fields = [
            "id",
            "user_id",
            "username",
            "age",
            "income",
            "loan_amount",
            "cibil_score",
            "prediction",
            "probability",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "username",
            "prediction",
            "probability",
            "created_at",
        ]

    def validate_age(self, value):
        if value < 18 or value > 100:
            raise serializers.ValidationError(
                "Age must be between 18 and 100."
            )
        return value

    def validate_income(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Income must be greater than 0."
            )
        return value

    def validate_loan_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Loan amount must be greater than 0."
            )
        return value

    def validate_cibil_score(self, value):
        if value < 300 or value > 900:
            raise serializers.ValidationError(
                "CIBIL score must be between 300 and 900."
            )
        return value
