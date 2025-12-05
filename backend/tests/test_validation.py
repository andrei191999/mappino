"""Tests for /api/v1/validation endpoints."""

import base64
import io

import pytest

API_PREFIX = "/api/v1/validation"


class TestValidationEndpoints:
    """Test validation router endpoints."""

    def test_list_validators(self, client):
        """GET /api/v1/validation/validators returns validator list."""
        response = client.get(f"{API_PREFIX}/validators")
        assert response.status_code == 200
        data = response.json()
        assert "validators" in data
        validators = data["validators"]
        assert len(validators) >= 2  # At least XSD and Helger

        # Check validator structure
        validator_types = [v["type"] for v in validators]
        assert "xsd" in validator_types
        assert "helger" in validator_types
        assert "schematron" in validator_types

    def test_list_vesids(self, client):
        """GET /api/v1/validation/vesids returns VESID list."""
        response = client.get(f"{API_PREFIX}/vesids")
        assert response.status_code == 200
        data = response.json()
        assert "vesids" in data
        assert len(data["vesids"]) > 0

        # Check VESID structure
        vesid = data["vesids"][0]
        assert "id" in vesid
        assert "name" in vesid
        assert "format" in vesid

    def test_list_mappers(self, client):
        """GET /api/v1/validation/mappers returns mapper list."""
        response = client.get(f"{API_PREFIX}/mappers")
        assert response.status_code == 200
        data = response.json()
        assert "mappers" in data


class TestValidation:
    """Test XML validation."""

    def test_validate_quick_wellformed_xml(self, client, sample_ubl_invoice):
        """POST /api/v1/validation/validate/quick with valid XML."""
        files = [("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml"))]

        response = client.post(f"{API_PREFIX}/validate/quick", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1

        result = data["results"][0]
        assert result["filename"] == "invoice.xml"
        assert "overall_success" in result

    def test_validate_quick_malformed_xml(self, client, malformed_xml):
        """POST /api/v1/validation/validate/quick with malformed XML."""
        files = [("files", ("bad.xml", io.BytesIO(malformed_xml), "application/xml"))]

        response = client.post(f"{API_PREFIX}/validate/quick", files=files)
        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]
        # Should report error
        assert result.get("overall_success") is False or "error" in result

    def test_validate_with_xsd_only(self, client, sample_ubl_invoice):
        """POST /api/v1/validation/validate with XSD validator."""
        files = [("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml"))]

        response = client.post(
            f"{API_PREFIX}/validate",
            files=files,
            data={"validators": "xsd"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_validate_multiple_files(self, client, sample_ubl_invoice, sample_credit_note):
        """POST /api/v1/validation/validate/quick with multiple files."""
        files = [
            ("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml")),
            ("files", ("creditnote.xml", io.BytesIO(sample_credit_note), "application/xml")),
        ]

        response = client.post(f"{API_PREFIX}/validate/quick", files=files)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2

    def test_validate_compare(self, client, sample_ubl_invoice):
        """POST /api/v1/validation/validate/compare runs multiple validators."""
        files = [("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml"))]

        response = client.post(
            f"{API_PREFIX}/validate/compare",
            files=files,
            data={"validators": "xsd,schematron"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


class TestTransformation:
    """Test XSLT transformation."""

    def test_transform_with_invalid_mapper(self, client, sample_ubl_invoice):
        """POST /api/v1/validation/transform with non-existent mapper."""
        files = [("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml"))]

        response = client.post(
            f"{API_PREFIX}/transform",
            files=files,
            data={"mapper": "nonexistent.xsl"}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]
        assert result["success"] is False
        assert result["error"] is not None

    def test_transform_download_invalid_mapper(self, client, sample_ubl_invoice):
        """POST /api/v1/validation/transform/download with non-existent mapper returns 404."""
        files = [("file", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml"))]

        response = client.post(
            f"{API_PREFIX}/transform/download",
            files=files,
            data={"mapper": "nonexistent.xsl"}
        )
        # Should return 404 for missing mapper
        assert response.status_code == 404


class TestHealthEndpoints:
    """Test health and root endpoints."""

    def test_health(self, client):
        """GET /health returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root(self, client):
        """GET / returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "api_version" in data
        assert "endpoints" in data
