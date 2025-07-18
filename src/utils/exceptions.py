"""
Exception classes for the Energy Saver rApp.

This module defines custom exceptions used throughout the application.
"""


class EnergySaverBaseException(Exception):
    """Base exception class for Energy Saver rApp."""
    
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ConfigurationError(EnergySaverBaseException):
    """Raised when there's a configuration-related error."""
    pass


class PrometheusConnectionError(EnergySaverBaseException):
    """Raised when unable to connect to Prometheus."""
    pass


class PrometheusQueryError(EnergySaverBaseException):
    """Raised when Prometheus query fails."""
    pass


class PolicyDeploymentError(EnergySaverBaseException):
    """Raised when policy deployment fails."""
    pass


class OptimizationError(EnergySaverBaseException):
    """Raised when optimization process fails."""
    pass


class MetricsCollectionError(EnergySaverBaseException):
    """Raised when metrics collection fails."""
    pass


class RAppRegistrationError(EnergySaverBaseException):
    """Raised when rApp registration fails."""
    pass
