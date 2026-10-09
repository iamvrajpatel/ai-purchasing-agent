class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"


class AuthorizationError(DomainError):
    code = "AUTHORIZATION_ERROR"


class AgentConfigurationError(DomainError):
    code = "AGENT_CONFIGURATION_ERROR"

