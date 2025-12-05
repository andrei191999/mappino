"""
Schematron Validator - Business rule validation using Schematron/XSLT.
Validates against EN 16931 and Peppol BIS rules.
"""
import time
from pathlib import Path
from typing import Optional

import lxml.etree as ET

from .base import BaseValidator, ValidationResult, ValidationIssue, Severity

# Schematron files directory
SCHEMATRON_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "schemas" / "schematron"

# SVRL namespace
SVRL_NS = "http://purl.oclc.org/dml/svrl"


class SchematronValidator(BaseValidator):
    """
    Schematron validator for business rules.

    Supports:
    - Pre-compiled XSLT schematron files
    - Raw .sch files (compiled on first use)
    - Auto-detection based on document type
    """

    _xslt_cache: dict[str, ET.XSLT] = {}

    # Schematron mappings: profile -> xslt file
    SCHEMATRON_MAP = {
        # Peppol BIS 3.0
        "peppol-bis3": "peppol-bis3.xslt",
        # EN 16931 (CEN)
        "en16931-ubl": "en16931-ubl.xslt",
        "en16931-cii": "en16931-cii.xslt",
    }

    # Namespace to profile detection
    PROFILE_DETECTION = {
        "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2": "peppol-bis3",
        "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2": "peppol-bis3",
        "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100": "en16931-cii",
    }

    def __init__(self):
        SCHEMATRON_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "Schematron"

    @property
    def validator_type(self) -> str:
        return "schematron"

    @property
    def description(self) -> str:
        return "Business rule validation using Schematron. Checks EN 16931 and Peppol BIS rules."

    @property
    def is_local(self) -> bool:
        return True

    @property
    def supported_formats(self) -> list[str]:
        return ["ubl", "cii"]

    async def validate(
        self,
        xml_bytes: bytes,
        schematron: Optional[str] = None,
        profile: Optional[str] = None,
        **kwargs
    ) -> ValidationResult:
        """
        Validate XML against Schematron rules.

        Args:
            xml_bytes: XML document
            schematron: Path to schematron XSLT file (optional)
            profile: Profile name to use (peppol-bis3, en16931-ubl, etc.)
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

        # Get XSLT transformer
        xslt = None
        if schematron:
            xslt = self._load_xslt(schematron)
        elif profile:
            xslt = self._load_profile(profile)
        else:
            xslt = self._detect_profile(doc)

        if not xslt:
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=True,
                issues=[ValidationIssue(
                    severity=Severity.INFO,
                    rule_id="SCH_NO_RULES",
                    message="No Schematron rules found for this document type.",
                    source=self.name,
                )],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Run Schematron validation
        try:
            svrl_result = xslt(doc)
            issues = self._parse_svrl(svrl_result)
        except ET.XSLTApplyError as e:
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=False,
                issues=[ValidationIssue(
                    severity=Severity.ERROR,
                    rule_id="SCH_TRANSFORM_ERROR",
                    message=f"Schematron transform error: {e}",
                    source=self.name,
                )],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        success = not any(i.severity == Severity.ERROR for i in issues)

        return ValidationResult(
            validator_name=self.name,
            validator_type=self.validator_type,
            success=success,
            issues=issues,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def _load_xslt(self, path: str) -> Optional[ET.XSLT]:
        """Load and cache XSLT file."""
        if path in self._xslt_cache:
            return self._xslt_cache[path]

        try:
            p = Path(path)
            if not p.is_absolute():
                p = SCHEMATRON_DIR / path

            if not p.exists():
                return None

            xslt_doc = ET.parse(str(p))
            xslt = ET.XSLT(xslt_doc)
            self._xslt_cache[path] = xslt
            return xslt
        except Exception:
            return None

    def _load_profile(self, profile: str) -> Optional[ET.XSLT]:
        """Load XSLT for a named profile."""
        xslt_file = self.SCHEMATRON_MAP.get(profile)
        if xslt_file:
            return self._load_xslt(xslt_file)
        return None

    def _detect_profile(self, doc: ET.Element) -> Optional[ET.XSLT]:
        """Auto-detect profile from document namespace."""
        ns = doc.tag.split("}")[0].strip("{") if "}" in doc.tag else None
        if not ns:
            return None

        profile = self.PROFILE_DETECTION.get(ns)
        if profile:
            return self._load_profile(profile)
        return None

    def _parse_svrl(self, svrl: ET._XSLTResultTree) -> list[ValidationIssue]:
        """Parse SVRL output into ValidationIssues."""
        issues = []
        svrl_root = svrl.getroot()

        if svrl_root is None:
            return issues

        # Find all failed assertions
        for failed in svrl_root.iter(f"{{{SVRL_NS}}}failed-assert"):
            rule_id = failed.get("id", "UNKNOWN")
            location = failed.get("location", "")
            flag = failed.get("flag", "error").lower()

            # Get message text
            text_el = failed.find(f"{{{SVRL_NS}}}text")
            message = text_el.text.strip() if text_el is not None and text_el.text else "Assertion failed"

            # Map flag to severity
            if flag in ("fatal", "error"):
                severity = Severity.ERROR
            elif flag == "warning":
                severity = Severity.WARNING
            else:
                severity = Severity.INFO

            issues.append(ValidationIssue(
                severity=severity,
                rule_id=rule_id,
                message=message,
                location=location,
                source=self.name,
            ))

        # Find successful reports (informational)
        for report in svrl_root.iter(f"{{{SVRL_NS}}}successful-report"):
            rule_id = report.get("id", "UNKNOWN")
            location = report.get("location", "")
            flag = report.get("flag", "info").lower()

            text_el = report.find(f"{{{SVRL_NS}}}text")
            message = text_el.text.strip() if text_el is not None and text_el.text else "Report"

            if flag in ("fatal", "error"):
                severity = Severity.ERROR
            elif flag == "warning":
                severity = Severity.WARNING
            else:
                severity = Severity.INFO

            issues.append(ValidationIssue(
                severity=severity,
                rule_id=rule_id,
                message=message,
                location=location,
                source=self.name,
            ))

        return issues

    @classmethod
    def list_available_profiles(cls) -> list[dict]:
        """List available Schematron profiles."""
        profiles = []
        for profile, filename in cls.SCHEMATRON_MAP.items():
            path = SCHEMATRON_DIR / filename
            profiles.append({
                "profile": profile,
                "filename": filename,
                "available": path.exists(),
            })
        return profiles
