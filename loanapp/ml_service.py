"""
Machine Learning Prediction Service for Loan Eligibility.
Handles model loading, feature validation, preprocessing, probability estimation,
and graceful error handling.
"""

import logging
import math
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "ml_models"
MODEL_PATH = MODEL_DIR / "loan_model.joblib" 

class LoanEligibilityPredictor:
    """
    Service for evaluating loan eligibility using machine learning or calibrated scoring.
    Caches loaded models to prevent per-request disk I/O.
    """
    _instance = None
    _model = None
    _is_model_loaded = False

    FEATURE_NAMES = ["age", "income", "loan_amount", "cibil_score"]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoanEligibilityPredictor, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Attempts to load a saved ML model artifact if available."""
        if MODEL_PATH.exists():
            try:
                import joblib
                self._model = joblib.load(MODEL_PATH)
                self._is_model_loaded = True
                logger.info("ML model successfully loaded from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load model from %s: %s. Using calibrated scoring engine.", MODEL_PATH, e)
                self._model = None
                self._is_model_loaded = False
        else:
            logger.info("No external ML artifact at %s. Calibrated scoring engine active.", MODEL_PATH)
            self._model = None
            self._is_model_loaded = False

    def validate_features(self, age: int, income: float, loan_amount: float, cibil_score: int) -> dict:
        """
        Validates feature ranges before inference.
        Raises ValueError on invalid ranges.
        """
        if not (18 <= age <= 100):
            raise ValueError(f"Age must be between 18 and 100. Received: {age}")
        if income <= 0:
            raise ValueError(f"Income must be greater than 0. Received: {income}")
        if loan_amount <= 0:
            raise ValueError(f"Loan amount must be greater than 0. Received: {loan_amount}")
        if not (300 <= cibil_score <= 900):
            raise ValueError(f"CIBIL score must be between 300 and 900. Received: {cibil_score}")

        return {
            "age": int(age),
            "income": float(income),
            "loan_amount": float(loan_amount),
            "cibil_score": int(cibil_score)
        }

    def predict(self, age: int, income: float, loan_amount: float, cibil_score: int) -> dict:
        """
        Generates eligibility prediction and calibrated probability.
        
        Returns:
            dict: {
                "prediction": "Eligible" | "Not Eligible",
                "probability": float (0.0 to 1.0),
                "disclaimer": str,
                "risk_factors": list[str]
            }
        """
        if isinstance(income, Decimal):
            income = float(income)
        if isinstance(loan_amount, Decimal):
            loan_amount = float(loan_amount)

        validated = self.validate_features(age, income, loan_amount, cibil_score)

        # 1. If external model is loaded, execute inference via scikit-learn pipeline
        if self._is_model_loaded and self._model is not None:
            try:
                features = [[
                    validated["age"],
                    validated["income"],
                    validated["loan_amount"],
                    validated["cibil_score"]
                ]]
                if hasattr(self._model, "predict_proba"):
                    proba = float(self._model.predict_proba(features)[0][1])
                else:
                    pred_val = self._model.predict(features)[0]
                    proba = 0.90 if pred_val in (1, "Eligible", True) else 0.20

                prediction = "Eligible" if proba >= 0.50 else "Not Eligible"
                return self._format_result(prediction, round(proba, 4), validated)
            except Exception as e:
                logger.error("Inference failed with loaded model: %s. Falling back to calibrated engine.", e)

        # 2. Calibrated Underwriting Scoring Pipeline (Logistic Scoring Model)
        # Standardized factors:
        # - CIBIL Score (Weight: 45%): 750+ prime, 700-749 good, 650-699 subprime, <650 high risk
        # - Debt-to-Income Ratio (Loan / Annual Income) (Weight: 35%)
        # - Income Base (Weight: 15%)
        # - Age Stability (Weight: 5%)
        
        cibil_norm = (validated["cibil_score"] - 300) / 600.0  # 0.0 to 1.0
        
        dti_ratio = validated["loan_amount"] / validated["income"]  # e.g. 2.5x annual income
        dti_score = 1.0 / (1.0 + math.exp((dti_ratio - 5.0) * 1.2))  # Sigmoid centered around 5x income
        
        income_score = min(1.0, math.log10(max(1000, validated["income"])) / 6.0)
        
        age_score = 1.0 if 25 <= validated["age"] <= 60 else 0.75

        # Combined logit score
        logit = (
            (cibil_norm - 0.55) * 4.5 +
            (dti_score - 0.5) * 3.5 +
            (income_score - 0.6) * 1.5 +
            (age_score - 0.8) * 0.5
        )

        probability = 1.0 / (1.0 + math.exp(-logit))
        probability = max(0.05, min(0.98, probability))
        
        # Determine eligibility threshold (standard 0.50)
        prediction = "Eligible" if probability >= 0.50 and validated["cibil_score"] >= 600 else "Not Eligible"

        return self._format_result(prediction, round(probability, 4), validated)
    def _format_result(self, prediction: str, probability: float, validated: dict) -> dict:
        risk_factors = []
        if validated["cibil_score"] < 650:                                                                         
            risk_factors.append("Low CIBIL credit score below prime threshold (650).")
        if validated["loan_amount"] > validated["income"] * 6:
            risk_factors.append("High loan amount relative to declared annual income.")
        if validated["income"] < 25000:
            risk_factors.append("Income is below recommended threshold.")

        return {
            "prediction": prediction,
            "probability": probability,
            "disclaimer": "This is a model-generated eligibility estimate and does not constitute a guaranteed loan approval.",
            "risk_factors": risk_factors
        }


# Global service instance
predictor = LoanEligibilityPredictor()
