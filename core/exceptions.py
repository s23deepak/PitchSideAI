"""
Error handling and custom exceptions.
"""


class PitchSideAIException(Exception):
    """Base exception for PitchSide AI."""

    def __init__(self, message: str, error_code: str = "UNKNOWN", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(PitchSideAIException):
    """Configuration-related error."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "CONFIG_ERROR", details)


class AgentExecutionError(PitchSideAIException):
    """Agent execution failed."""

    def __init__(self, agent: str, message: str, details: dict = None):
        details = details or {}
        details["agent"] = agent
        super().__init__(message, "AGENT_EXECUTION_ERROR", details)


class WorkflowExecutionError(PitchSideAIException):
    """Workflow execution failed."""

    def __init__(self, workflow_id: str, message: str, details: dict = None):
        details = details or {}
        details["workflow_id"] = workflow_id
        super().__init__(message, "WORKFLOW_EXECUTION_ERROR", details)


class RateLimitError(PitchSideAIException):
    """Rate limit exceeded."""

    def __init__(self, client_id: str, limit: int, message: str = None):
        msg = message or f"Rate limit exceeded for client {client_id} ({limit} req/min)"
        details = {"client_id": client_id, "limit": limit}
        super().__init__(msg, "RATE_LIMIT_ERROR", details)


class ModelAPIError(PitchSideAIException):
    """Error communicating with model API (Bedrock)."""

    def __init__(self, model_id: str, message: str, details: dict = None):
        details = details or {}
        details["model_id"] = model_id
        super().__init__(message, "MODEL_API_ERROR", details)


class RAGError(PitchSideAIException):
    """RAG/Vector store error."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "RAG_ERROR", details)


class TimeoutError(PitchSideAIException):
    """Operation timeout."""

    def __init__(self, operation: str, timeout_seconds: int):
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        details = {"operation": operation, "timeout_seconds": timeout_seconds}
        super().__init__(message, "TIMEOUT_ERROR", details)


def get_error_response(exc: Exception) -> dict:
    """Convert exception to API response."""
    if isinstance(exc, PitchSideAIException):
        return {
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    else:
        return {
            "error": "INTERNAL_ERROR",
            "message": str(exc),
            "details": {}
        }
