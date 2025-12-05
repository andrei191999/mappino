"""
Validator Registry - Manages multiple validators and runs them in parallel.
Supports result overlay/comparison across validators.
"""
import asyncio
from typing import Optional
from dataclasses import dataclass, field

from .base import BaseValidator, ValidationResult, ValidationIssue, Severity


@dataclass
class MultiValidationResult:
    """Combined results from multiple validators"""
    results: list[ValidationResult] = field(default_factory=list)
    overall_success: bool = True
    total_errors: int = 0
    total_warnings: int = 0

    def to_dict(self) -> dict:
        return {
            "overall_success": self.overall_success,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "validator_count": len(self.results),
            "results": [r.to_dict() for r in self.results],
            "issues_by_rule": self._group_issues_by_rule(),
        }

    def _group_issues_by_rule(self) -> dict:
        """Group issues by rule ID to see which validators agree"""
        rule_map: dict[str, list[dict]] = {}
        for result in self.results:
            for issue in result.issues:
                if issue.rule_id not in rule_map:
                    rule_map[issue.rule_id] = []
                rule_map[issue.rule_id].append({
                    "validator": result.validator_name,
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "location": issue.location,
                })
        return rule_map


class ValidatorRegistry:
    """Central registry for all validators"""

    def __init__(self):
        self._validators: dict[str, BaseValidator] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in validators"""
        from .helger import HelgerValidator
        from .xsd import XSDValidator
        from .schematron import SchematronValidator

        self.register(HelgerValidator())
        self.register(XSDValidator())
        self.register(SchematronValidator())

    def register(self, validator: BaseValidator):
        """Register a validator"""
        self._validators[validator.validator_type] = validator

    def get(self, validator_type: str) -> Optional[BaseValidator]:
        """Get validator by type"""
        return self._validators.get(validator_type)

    def list_validators(self) -> list[dict]:
        """List all registered validators"""
        return [v.get_info() for v in self._validators.values()]

    def get_local_validators(self) -> list[BaseValidator]:
        """Get validators that run locally (no API calls)"""
        return [v for v in self._validators.values() if v.is_local]

    def get_external_validators(self) -> list[BaseValidator]:
        """Get validators that use external APIs"""
        return [v for v in self._validators.values() if not v.is_local]

    async def validate(
        self,
        xml_bytes: bytes,
        validator_types: Optional[list[str]] = None,
        **kwargs
    ) -> MultiValidationResult:
        """
        Run validation with specified validators.

        Args:
            xml_bytes: XML document
            validator_types: List of validator types to run (None = all)
            **kwargs: Passed to validators (vesid, schema_path, etc.)
        """
        if validator_types:
            validators = [self._validators[t] for t in validator_types if t in self._validators]
        else:
            validators = list(self._validators.values())

        if not validators:
            return MultiValidationResult(overall_success=False)

        # Run validators (local ones can be parallel, external ones should be sequential)
        results = []

        # First run local validators in parallel
        local = [v for v in validators if v.is_local]
        external = [v for v in validators if not v.is_local]

        if local:
            local_tasks = [v.validate(xml_bytes, **kwargs) for v in local]
            local_results = await asyncio.gather(*local_tasks, return_exceptions=True)
            for r in local_results:
                if isinstance(r, ValidationResult):
                    results.append(r)
                elif isinstance(r, Exception):
                    # Handle exception from validator
                    results.append(ValidationResult(
                        validator_name="Unknown",
                        validator_type="error",
                        success=False,
                        issues=[ValidationIssue(
                            severity=Severity.ERROR,
                            rule_id="VALIDATOR_ERROR",
                            message=str(r),
                        )],
                    ))

        # Run external validators sequentially (respect rate limits)
        for v in external:
            try:
                result = await v.validate(xml_bytes, **kwargs)
                results.append(result)
            except Exception as e:
                results.append(ValidationResult(
                    validator_name=v.name,
                    validator_type=v.validator_type,
                    success=False,
                    issues=[ValidationIssue(
                        severity=Severity.ERROR,
                        rule_id="VALIDATOR_ERROR",
                        message=str(e),
                        source=v.name,
                    )],
                ))

        # Aggregate results
        overall_success = all(r.success for r in results)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        return MultiValidationResult(
            results=results,
            overall_success=overall_success,
            total_errors=total_errors,
            total_warnings=total_warnings,
        )

    async def validate_local_only(self, xml_bytes: bytes, **kwargs) -> MultiValidationResult:
        """Run only local validators (fast, no rate limits)"""
        local_types = [v.validator_type for v in self.get_local_validators()]
        return await self.validate(xml_bytes, validator_types=local_types, **kwargs)

    async def validate_with_comparison(
        self,
        xml_bytes: bytes,
        validator_types: list[str],
        **kwargs
    ) -> dict:
        """
        Run multiple validators and compare results.
        Returns detailed comparison showing agreement/disagreement.
        """
        result = await self.validate(xml_bytes, validator_types=validator_types, **kwargs)

        # Build comparison matrix
        all_rule_ids = set()
        for r in result.results:
            for issue in r.issues:
                all_rule_ids.add(issue.rule_id)

        comparison = []
        for rule_id in sorted(all_rule_ids):
            row = {"rule_id": rule_id, "validators": {}}
            for r in result.results:
                matching = [i for i in r.issues if i.rule_id == rule_id]
                if matching:
                    row["validators"][r.validator_name] = {
                        "found": True,
                        "severity": matching[0].severity.value,
                        "message": matching[0].message,
                    }
                else:
                    row["validators"][r.validator_name] = {"found": False}
            comparison.append(row)

        return {
            **result.to_dict(),
            "comparison": comparison,
        }
