"""
Helger WSDVS Validator - External API-based validation
Supports many VESIDs: Peppol BIS3, EN16931, ZUGFeRD, XRechnung, etc.
"""
import logging
import time
from typing import Optional

import zeep
import zeep.helpers

from .base import BaseValidator, ValidationResult, ValidationIssue, Severity

WSDL_URL = "https://peppol.helger.com/wsdvs?wsdl"
ENDPOINT = "https://peppol.helger.com/wsdvs"

logging.getLogger("zeep").setLevel(logging.ERROR)


class HelgerValidator(BaseValidator):
    """Validator using Helger's WSDVS SOAP service"""

    _client = None
    _service = None

    # Common VESIDs
    VESIDS = {
        "peppol_invoice": "eu.peppol.bis3:invoice:2025.5",
        "peppol_creditnote": "eu.peppol.bis3:creditnote:2025.5",
        "en16931_ubl": "eu.cen.en16931:ubl:1.3.15",
        "en16931_cii": "eu.cen.en16931:cii:1.3.15",
        "zugferd_en16931": "de.zugferd:en16931:2.3.3",
        "zugferd_extended": "de.zugferd:extended:2.3.3",
        "facturx_en16931": "fr.factur-x:en16931:1.0.7-3",
        "xrechnung_ubl": "de.xrechnung:ubl-invoice:3.0.2",
    }

    def __init__(self, rate_limit_ms: int = 550):
        self.rate_limit_ms = rate_limit_ms
        if HelgerValidator._client is None:
            HelgerValidator._client = zeep.Client(wsdl=WSDL_URL)
            HelgerValidator._service = HelgerValidator._client.create_service(
                "{http://ws.peppol.helger.com/}WSDVSPortBinding", ENDPOINT
            )

    @property
    def name(self) -> str:
        return "Helger WSDVS"

    @property
    def validator_type(self) -> str:
        return "helger"

    @property
    def description(self) -> str:
        return "External validation via Helger's WSDVS SOAP service. Supports many standards."

    @property
    def is_local(self) -> bool:
        return False

    @property
    def supported_formats(self) -> list[str]:
        return ["ubl", "cii", "zugferd", "facturx"]

    async def validate(self, xml_bytes: bytes, vesid: Optional[str] = None, **kwargs) -> ValidationResult:
        """
        Validate using Helger WSDVS.

        Args:
            xml_bytes: XML document
            vesid: Validation artefact ID (e.g., 'eu.peppol.bis3:invoice:2025.5')
        """
        start_time = time.time()

        if not vesid:
            vesid = self.VESIDS["peppol_invoice"]

        xml_string = xml_bytes.decode("utf-8")

        # Rate limit
        time.sleep(self.rate_limit_ms / 1000.0)

        try:
            report = self._service.validate(XML=xml_string, VESID=vesid, displayLocale="en")
        except Exception as e:
            return ValidationResult(
                validator_name=self.name,
                validator_type=self.validator_type,
                success=False,
                issues=[ValidationIssue(
                    severity=Severity.ERROR,
                    rule_id="HELGER_CONNECTION",
                    message=f"Validation service error: {e}",
                    source=self.name,
                )],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Parse response
        issues = []
        result_dict = zeep.helpers.serialize_object(report)

        for item in result_dict.get("Result", []):
            # Handle nested items (schematron artefacts)
            if item.get("Item"):
                for sub in item["Item"]:
                    issue = self._parse_issue(sub)
                    if issue:
                        issues.append(issue)
            else:
                issue = self._parse_issue(item)
                if issue:
                    issues.append(issue)

        errors = [i for i in issues if i.severity == Severity.ERROR]

        return ValidationResult(
            validator_name=self.name,
            validator_type=self.validator_type,
            success=len(errors) == 0,
            issues=issues,
            raw_response=result_dict,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def _parse_issue(self, item: dict) -> Optional[ValidationIssue]:
        level = item.get("errorLevel") or item.get("mostSevereErrorLevel")
        error_id = item.get("errorID", "")
        text = item.get("errorText", "")
        location = item.get("errorLocation", "")

        if not level:
            return None

        severity = Severity.ERROR if level == "ERROR" else (
            Severity.WARNING if level == "WARN" else Severity.INFO
        )

        return ValidationIssue(
            severity=severity,
            rule_id=error_id,
            message=text,
            location=location if location else None,
            source=self.name,
        )

    @classmethod
    def get_vesid_list(cls) -> list[dict]:
        """Get list of common VESIDs"""
        return [
            {"id": v, "alias": k, "name": k.replace("_", " ").title()}
            for k, v in cls.VESIDS.items()
        ]
