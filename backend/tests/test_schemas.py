"""Tests for schema management endpoints and rules sync service."""

import pytest

API_PREFIX = "/api/v1/schemas"


class TestRulesSyncService:
    """Test rules sync service directly."""

    def test_get_status(self):
        """Get sync status returns expected structure."""
        from app.services.rules_sync import get_rules_sync_service

        service = get_rules_sync_service()
        status = service.get_status()

        assert "sources" in status
        assert "xsd_schemas" in status
        assert "schematron_rules" in status
        assert isinstance(status["sources"], list)

    def test_sources_have_required_fields(self):
        """All sources have required fields."""
        from app.services.rules_sync import get_rules_sync_service

        service = get_rules_sync_service()
        status = service.get_status()

        for source in status["sources"]:
            assert "id" in source
            assert "name" in source
            assert "type" in source
            assert "status" in source

    def test_count_files(self):
        """Count files works correctly."""
        from app.services.rules_sync import get_rules_sync_service
        from pathlib import Path

        service = get_rules_sync_service()

        # Create temp dir with some files
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test1.xsd").touch()
            (tmppath / "test2.xsd").touch()
            (tmppath / "other.txt").touch()

            count = service._count_files(tmppath, "*.xsd")
            assert count == 2


class TestSchemasEndpoints:
    """Test schema API endpoints."""

    def test_get_status(self, client):
        """GET /schemas/status returns status."""
        response = client.get(f"{API_PREFIX}/status")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "xsd_schemas" in data
        assert "schematron_rules" in data

    def test_list_xsd_schemas(self, client):
        """GET /schemas/xsd lists XSD schemas."""
        response = client.get(f"{API_PREFIX}/xsd")
        assert response.status_code == 200
        data = response.json()
        assert "schemas" in data
        assert "count" in data
        assert isinstance(data["schemas"], list)

    def test_list_schematron_rules(self, client):
        """GET /schemas/schematron lists schematron rules."""
        response = client.get(f"{API_PREFIX}/schematron")
        assert response.status_code == 200
        data = response.json()
        assert "rule_sets" in data
        assert isinstance(data["rule_sets"], list)

    def test_sync_unknown_source(self, client):
        """POST /schemas/sync/{source} with unknown source."""
        response = client.post(f"{API_PREFIX}/sync/unknown_source")
        assert response.status_code == 500
        assert "Unknown source" in response.json()["detail"]


class TestValidatorIntegration:
    """Test validators work correctly."""

    def test_xsd_validator_info(self):
        """XSD validator has correct info."""
        from app.services.validators import XSDValidator

        validator = XSDValidator()
        info = validator.get_info()

        assert info["name"] == "XSD Schema"
        assert info["type"] == "xsd"
        assert info["is_local"] is True

    def test_schematron_validator_info(self):
        """Schematron validator has correct info."""
        from app.services.validators.schematron import SchematronValidator

        validator = SchematronValidator()
        info = validator.get_info()

        assert info["name"] == "Schematron"
        assert info["type"] == "schematron"
        assert info["is_local"] is True

    def test_helger_validator_info(self):
        """Helger validator has correct info."""
        from app.services.validators import HelgerValidator

        validator = HelgerValidator()
        info = validator.get_info()

        assert info["name"] == "Helger WSDVS"
        assert info["type"] == "helger"
        assert info["is_local"] is False

    def test_registry_has_all_validators(self):
        """Validator registry has all validators."""
        from app.services.validators import ValidatorRegistry

        registry = ValidatorRegistry()
        validators = registry.list_validators()

        types = [v["type"] for v in validators]
        assert "xsd" in types
        assert "helger" in types
        assert "schematron" in types

    def test_registry_local_validators(self):
        """Registry correctly identifies local validators."""
        from app.services.validators import ValidatorRegistry

        registry = ValidatorRegistry()
        local = registry.get_local_validators()
        external = registry.get_external_validators()

        local_types = [v.validator_type for v in local]
        external_types = [v.validator_type for v in external]

        assert "xsd" in local_types
        assert "schematron" in local_types
        assert "helger" in external_types

    @pytest.mark.asyncio
    async def test_xsd_validates_wellformed_xml(self):
        """XSD validator validates well-formed XML."""
        from app.services.validators import XSDValidator

        validator = XSDValidator()
        xml = b'<?xml version="1.0"?><root><item>test</item></root>'

        result = await validator.validate(xml)

        assert result.validator_name == "XSD Schema"
        assert result.success  # Well-formed XML passes
        assert result.execution_time_ms is not None

    @pytest.mark.asyncio
    async def test_xsd_rejects_malformed_xml(self):
        """XSD validator rejects malformed XML."""
        from app.services.validators import XSDValidator

        validator = XSDValidator()
        xml = b'<invalid><unclosed>'

        result = await validator.validate(xml)

        assert not result.success
        assert len(result.errors) > 0
        assert result.errors[0].rule_id == "XML_SYNTAX"

    @pytest.mark.asyncio
    async def test_schematron_validates_xml(self):
        """Schematron validator validates XML."""
        from app.services.validators.schematron import SchematronValidator

        validator = SchematronValidator()
        xml = b'<?xml version="1.0"?><root/>'

        result = await validator.validate(xml)

        assert result.validator_name == "Schematron"
        # Without rules, should succeed with info message
        assert result.success

    @pytest.mark.asyncio
    async def test_registry_validate_local_only(self):
        """Registry validate_local_only uses only local validators."""
        from app.services.validators import ValidatorRegistry

        registry = ValidatorRegistry()
        xml = b'<?xml version="1.0"?><root/>'

        result = await registry.validate_local_only(xml)

        # Should only use local validators (xsd, schematron)
        validator_types = [r.validator_type for r in result.results]
        assert "helger" not in validator_types
        assert "xsd" in validator_types
