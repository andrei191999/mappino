"""
Base validator interface for multi-validator architecture.
All validators must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    severity: Severity
    rule_id: str
    message: str
    location: Optional[str] = None  # XPath or line number
    source: Optional[str] = None    # Which validator produced this


@dataclass
class ValidationResult:
    validator_name: str
    validator_type: str  # helger, xsd, schematron, etc.
    success: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    raw_response: Optional[dict] = None
    execution_time_ms: Optional[float] = None

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    def to_dict(self) -> dict:
        return {
            "validator_name": self.validator_name,
            "validator_type": self.validator_type,
            "success": self.success,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "severity": i.severity.value,
                    "rule_id": i.rule_id,
                    "message": i.message,
                    "location": i.location,
                    "source": i.source,
                }
                for i in self.issues
            ],
            "execution_time_ms": self.execution_time_ms,
        }


class BaseValidator(ABC):
    """Abstract base class for all validators"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name"""
        pass

    @property
    @abstractmethod
    def validator_type(self) -> str:
        """Type identifier (helger, xsd, schematron, etc.)"""
        pass

    @property
    def description(self) -> str:
        """Optional description"""
        return ""

    @property
    def is_local(self) -> bool:
        """Whether this validator runs locally (no external API)"""
        return True

    @property
    def supported_formats(self) -> list[str]:
        """List of supported document formats (ubl, cii, etc.)"""
        return ["xml"]

    @abstractmethod
    async def validate(self, xml_bytes: bytes, **kwargs) -> ValidationResult:
        """
        Validate XML document.

        Args:
            xml_bytes: The XML document as bytes
            **kwargs: Validator-specific options (vesid, schema_path, etc.)

        Returns:
            ValidationResult with issues found
        """
        pass

    def get_info(self) -> dict:
        """Get validator metadata"""
        return {
            "name": self.name,
            "type": self.validator_type,
            "description": self.description,
            "is_local": self.is_local,
            "supported_formats": self.supported_formats,
        }
