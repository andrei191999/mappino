"""
XSD Validator - Local XML Schema validation using lxml
Fast structural validation without external API calls.
"""
import time
from pathlib import Path
from typing import Optional

import lxml.etree as ET

from .base import BaseValidator, ValidationResult, ValidationIssue, Severity

# XSD files directory
XSD_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "schemas" / "xsd"


class XSDValidator(BaseValidator):
    """Local XSD Schema validator using lxml"""

    _schema_cache: dict[str, ET.XMLSchema] = {}

    # Built-in schema mappings (namespace -> schema file)
    SCHEMA_MAP = {
        # UBL 2.1
        "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2": "UBL-Invoice-2.1.xsd",
        "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2": "UBL-CreditNote-2.1.xsd",
        # Add more as needed
    }

    def __init__(self):
        XSD_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "XSD Schema"

    @property
    def validator_type(self) -> str:
        return "xsd"

    @property
    def description(self) -> str:
        return "Local XML Schema validation. Fast structural check, no business rules."

    @property
    def is_local(self) -> bool:
        return True

    @property
    def supported_formats(self) -> list[str]:
        return ["xml", "ubl", "cii"]

    async def validate(
        self,
        xml_bytes: bytes,
        schema_path: Optional[str] = None,
        auto_detect: bool = True,
        **kwargs
    ) -> ValidationResult:
        """
        Validate XML against XSD schema.

        Args:
            xml_bytes: XML document
            schema_path: Path to XSD file (optional)
            auto_detect: Try to detect schema from namespace (default True)
        """
        start_time = time.time()
        issues = []

        try:
            doc = ET.fromstring(xml_bytes)
        except ET.XMLSyntaxError as e:
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=False,
                issues=[ValidationIssue(
                    severity=Severity.ERROR,
                    rule_id="XML_SYNTAX",
                    message=f"XML parsing error: {e}",
                    location=f"line {e.lineno}" if hasattr(e, 'lineno') else None,
                    source=self.name,
                )],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Get schema
        schema = None
        if schema_path:
            schema = self._load_schema(schema_path)
        elif auto_detect:
            schema = self._detect_schema(doc)

        if not schema:
            # Just do well-formedness check (already passed if we got here)
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=True,
                issues=[ValidationIssue(
                    severity=Severity.INFO,
                    rule_id="XSD_NO_SCHEMA",
                    message="XML is well-formed. No XSD schema found for validation.",
                    source=self.name,
                )],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Validate against schema
        try:
            schema.assertValid(doc)
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=True,
                issues=[],
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except ET.DocumentInvalid as e:
            for error in schema.error_log:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    rule_id="XSD_INVALID",
                    message=error.message,
                    location=f"line {error.line}, column {error.column}",
                    source=self.name,
                ))

            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=False,
                issues=issues,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _load_schema(self, schema_path: str) -> Optional[ET.XMLSchema]:
        """Load and cache XSD schema"""
        if schema_path in self._schema_cache:
            return self._schema_cache[schema_path]

        try:
            path = Path(schema_path)
            if not path.is_absolute():
                path = XSD_DIR / schema_path

            if not path.exists():
                return None

            schema_doc = ET.parse(str(path))
            schema = ET.XMLSchema(schema_doc)
            self._schema_cache[schema_path] = schema
            return schema
        except Exception:
            return None

    def _detect_schema(self, doc: ET.Element) -> Optional[ET.XMLSchema]:
        """Try to detect schema from document namespace"""
        ns = doc.tag.split("}")[0].strip("{") if "}" in doc.tag else None
        if not ns:
            return None

        schema_file = self.SCHEMA_MAP.get(ns)
        if schema_file:
            return self._load_schema(schema_file)

        return None

    @classmethod
    def list_available_schemas(cls) -> list[dict]:
        """List available XSD schemas"""
        schemas = []
        if XSD_DIR.exists():
            for xsd in XSD_DIR.glob("*.xsd"):
                schemas.append({
                    "name": xsd.stem,
                    "path": str(xsd),
                    "filename": xsd.name,
                })
        return schemas
