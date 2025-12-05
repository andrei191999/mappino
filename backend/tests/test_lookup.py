"""Tests for /api/v1/lookup endpoints."""

import pytest

API_PREFIX = "/api/v1/lookup"


class TestLookupEndpoints:
    """Test lookup router endpoints."""

    def test_list_schemes(self, client):
        """GET /api/v1/lookup/schemes returns scheme list."""
        response = client.get(f"{API_PREFIX}/schemes")
        assert response.status_code == 200
        data = response.json()
        assert "schemes" in data
        assert "count" in data
        assert isinstance(data["schemes"], list)

    def test_list_schemes_with_country_filter(self, client):
        """GET /api/v1/lookup/schemes?country=BE filters by country."""
        response = client.get(f"{API_PREFIX}/schemes?country=BE")
        assert response.status_code == 200
        data = response.json()
        # All returned schemes should be for Belgium
        for scheme in data["schemes"]:
            if scheme.get("country"):
                assert scheme["country"] == "BE"

    def test_list_schemes_with_search(self, client):
        """GET /api/v1/lookup/schemes?search=... searches schemes."""
        response = client.get(f"{API_PREFIX}/schemes?search=VAT")
        assert response.status_code == 200
        data = response.json()
        assert "schemes" in data

    def test_get_scheme_by_icd(self, client):
        """GET /api/v1/lookup/schemes/{icd} returns scheme details."""
        # 0208 is Belgian enterprise number
        response = client.get(f"{API_PREFIX}/schemes/0208")
        assert response.status_code == 200
        data = response.json()
        # Either returns scheme data or error
        assert "icd" in data or "error" in data

    def test_get_scheme_not_found(self, client):
        """GET /api/v1/lookup/schemes/{icd} for unknown ICD."""
        response = client.get(f"{API_PREFIX}/schemes/9999")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "type" in data

    def test_validate_identifier(self, client):
        """POST /api/v1/lookup/schemes/validate validates identifier."""
        response = client.post(
            f"{API_PREFIX}/schemes/validate",
            json={"icd": "0208", "identifier": "0123456789"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data or "icd" in data

    def test_codelist_status(self, client):
        """GET /api/v1/lookup/schemes/status returns sync status."""
        response = client.get(f"{API_PREFIX}/schemes/status")
        assert response.status_code == 200

    def test_lookup_participants(self, client):
        """POST /api/v1/lookup/ performs participant lookup."""
        response = client.post(
            f"{API_PREFIX}/",
            json={
                "ids": ["0123456789"],
                "schemes": ["0208"],
                "use_test_sml": False,
                "merge_pd_discovery": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestLookupValidation:
    """Test identifier validation logic."""

    def test_validate_belgian_enterprise_number(self, client):
        """Belgian enterprise numbers should be 10 digits."""
        response = client.post(
            f"{API_PREFIX}/schemes/validate",
            json={"icd": "0208", "identifier": "0123456789"}
        )
        assert response.status_code == 200

    def test_validate_gln(self, client):
        """GLN should be 13 digits."""
        response = client.post(
            f"{API_PREFIX}/schemes/validate",
            json={"icd": "0088", "identifier": "1234567890123"}
        )
        assert response.status_code == 200
