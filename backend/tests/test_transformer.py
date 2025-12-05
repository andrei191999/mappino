"""Tests for the transformer service (XSLT 1.0/2.0/3.0)."""

import io
import pytest

API_PREFIX = "/api/v1/validation"


class TestTransformerService:
    """Test transformer service directly."""

    def test_detect_xslt_version_1(self):
        """Detect XSLT 1.0 version."""
        from app.services.transformer import get_transformer, XSLTVersion

        transformer = get_transformer()
        xslt_1 = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/">
                <output><xsl:copy-of select="."/></output>
            </xsl:template>
        </xsl:stylesheet>'''

        version = transformer.detect_xslt_version(xslt_1)
        assert version == XSLTVersion.V1_0

    def test_detect_xslt_version_2(self):
        """Detect XSLT 2.0 version."""
        from app.services.transformer import get_transformer, XSLTVersion

        transformer = get_transformer()
        xslt_2 = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/">
                <output/>
            </xsl:template>
        </xsl:stylesheet>'''

        version = transformer.detect_xslt_version(xslt_2)
        assert version == XSLTVersion.V2_0

    def test_detect_xslt_version_3(self):
        """Detect XSLT 3.0 version."""
        from app.services.transformer import get_transformer, XSLTVersion

        transformer = get_transformer()
        xslt_3 = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/">
                <output/>
            </xsl:template>
        </xsl:stylesheet>'''

        version = transformer.detect_xslt_version(xslt_3)
        assert version == XSLTVersion.V3_0

    def test_transform_xslt_1_success(self):
        """Transform using XSLT 1.0."""
        from app.services.transformer import get_transformer

        transformer = get_transformer()

        xml = b'<?xml version="1.0"?><root><item>test</item></root>'
        xslt = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/">
                <transformed><xsl:value-of select="//item"/></transformed>
            </xsl:template>
        </xsl:stylesheet>'''

        result = transformer.transform(xml, xslt)
        assert result.success
        assert result.processor == "lxml"
        assert b"<transformed>test</transformed>" in result.output

    def test_transform_invalid_xml(self):
        """Transform with invalid XML should fail."""
        from app.services.transformer import get_transformer

        transformer = get_transformer()

        xml = b'<invalid><unclosed>'
        xslt = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/"><out/></xsl:template>
        </xsl:stylesheet>'''

        result = transformer.transform(xml, xslt)
        assert not result.success
        assert "parse error" in result.error.lower() or "xml" in result.error.lower()

    def test_transform_invalid_xslt(self):
        """Transform with invalid XSLT should fail."""
        from app.services.transformer import get_transformer

        transformer = get_transformer()

        xml = b'<?xml version="1.0"?><root/>'
        xslt = b'not valid xslt at all'

        result = transformer.transform(xml, xslt)
        assert not result.success

    def test_list_mappers(self):
        """List mappers returns correct structure."""
        from app.services.transformer import get_transformer

        transformer = get_transformer()
        mappers = transformer.list_mappers()

        assert isinstance(mappers, list)
        # Each mapper should have name, type, xslt_version
        for mapper in mappers:
            assert "name" in mapper
            assert "type" in mapper
            assert "xslt_version" in mapper

    def test_save_and_delete_user_mapper(self):
        """Save and delete user mapper."""
        from app.services.transformer import get_transformer

        transformer = get_transformer()

        xslt = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/"><test/></xsl:template>
        </xsl:stylesheet>'''

        # Save
        path = transformer.save_user_mapper("test_mapper.xsl", xslt)
        assert path.exists()
        assert path.name == "test_mapper.xsl"

        # Delete
        deleted = transformer.delete_user_mapper("test_mapper.xsl")
        assert deleted
        assert not path.exists()

    def test_saxon_availability_check(self):
        """Check Saxon availability."""
        from app.services.transformer import TransformerService

        # Should return True or False, not raise
        available = TransformerService.is_saxon_available()
        assert isinstance(available, bool)


class TestTransformEndpoints:
    """Test transform API endpoints."""

    def test_list_mappers_endpoint(self, client):
        """GET /mappers returns mapper list with version info."""
        response = client.get(f"{API_PREFIX}/mappers")
        assert response.status_code == 200
        data = response.json()
        assert "mappers" in data
        assert "saxon_available" in data
        assert "supported_versions" in data
        assert "1.0" in data["supported_versions"]

    def test_upload_mapper(self, client):
        """POST /mappers/upload saves a mapper."""
        xslt = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/"><uploaded/></xsl:template>
        </xsl:stylesheet>'''

        files = [("file", ("upload_test.xsl", io.BytesIO(xslt), "application/xml"))]
        response = client.post(f"{API_PREFIX}/mappers/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["xslt_version"] == "1.0"
        assert data["type"] == "user"

        # Cleanup
        client.delete(f"{API_PREFIX}/mappers/{data['name']}")

    def test_delete_mapper_not_found(self, client):
        """DELETE /mappers/{name} for non-existent mapper."""
        response = client.delete(f"{API_PREFIX}/mappers/nonexistent_mapper.xsl")
        assert response.status_code == 404

    def test_transform_inline(self, client, sample_ubl_invoice):
        """POST /transform/inline transforms without saving mapper."""
        xslt = b'''<?xml version="1.0"?>
        <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="/"><inline-result/></xsl:template>
        </xsl:stylesheet>'''

        files = [
            ("files", ("invoice.xml", io.BytesIO(sample_ubl_invoice), "application/xml")),
            ("xslt", ("transform.xsl", io.BytesIO(xslt), "application/xml")),
        ]
        response = client.post(f"{API_PREFIX}/transform/inline", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["success"]
        assert result["processor"] == "lxml"

    def test_transform_zip(self, client):
        """POST /transform/zip transforms XMLs from ZIP."""
        import zipfile
        import io as std_io

        # Create a test ZIP
        zip_buffer = std_io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Add XSLT
            xslt = '''<?xml version="1.0"?>
            <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
                <xsl:template match="/"><zip-result/></xsl:template>
            </xsl:stylesheet>'''
            zf.writestr("transform.xsl", xslt)

            # Add XML
            xml = '<?xml version="1.0"?><test>content</test>'
            zf.writestr("document.xml", xml)

        zip_buffer.seek(0)

        files = [("file", ("test.zip", zip_buffer, "application/zip"))]
        response = client.post(f"{API_PREFIX}/transform/zip", files=files)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    def test_transform_zip_no_xslt(self, client):
        """POST /transform/zip without XSLT should fail."""
        import zipfile
        import io as std_io

        zip_buffer = std_io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("document.xml", '<?xml version="1.0"?><test/>')

        zip_buffer.seek(0)

        files = [("file", ("test.zip", zip_buffer, "application/zip"))]
        response = client.post(f"{API_PREFIX}/transform/zip", files=files)

        assert response.status_code == 400
        assert "XSLT" in response.json()["detail"]

    def test_transform_zip_no_xml(self, client):
        """POST /transform/zip without XML should fail."""
        import zipfile
        import io as std_io

        zip_buffer = std_io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            xslt = '''<?xml version="1.0"?>
            <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
                <xsl:template match="/"><out/></xsl:template>
            </xsl:stylesheet>'''
            zf.writestr("transform.xsl", xslt)

        zip_buffer.seek(0)

        files = [("file", ("test.zip", zip_buffer, "application/zip"))]
        response = client.post(f"{API_PREFIX}/transform/zip", files=files)

        assert response.status_code == 400
        assert "XML" in response.json()["detail"]
