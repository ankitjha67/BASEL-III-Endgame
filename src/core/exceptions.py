"""Custom exceptions for Basel III Endgame engine."""


class BaselEngineError(Exception):
    """Base exception for all engine errors."""


class ValidationError(BaselEngineError):
    """Raised when input data fails validation."""


class ConfigurationError(BaselEngineError):
    """Raised when regulatory parameters are missing or invalid."""


class CalculationError(BaselEngineError):
    """Raised when a calculation fails (e.g., non-PSD correlation matrix)."""


class DataError(BaselEngineError):
    """Raised when required data is missing or malformed."""
