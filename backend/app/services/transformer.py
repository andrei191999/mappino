"""
XSLT Transformer Service - Supports XSLT 1.0, 2.0, and 3.0

Uses lxml for XSLT 1.0 (fast, no Java dependency)
Uses saxonche for XSLT 2.0/3.0 (Saxon C library)
"""
import re
import hashlib
from pathlib import Path
from typing import Optional
from enum import Enum
from dataclasses import dataclass

import lxml.etree as ET

# Try to import saxonche (optional dependency for XSLT 2.0/3.0)
try:
    from saxonche import PySaxonProcessor
    SAXON_AVAILABLE = True
except ImportError:
    SAXON_AVAILABLE = False
    PySaxonProcessor = None


class XSLTVersion(str, Enum):
    V1_0 = "1.0"
    V2_0 = "2.0"
    V3_0 = "3.0"


@dataclass
class TransformResult:
    success: bool
    output: Optional[bytes] = None
    error: Optional[str] = None
    xslt_version: Optional[XSLTVersion] = None
    processor: Optional[str] = None  # "lxml" or "saxon"


class TransformerService:
    """
    Multi-version XSLT transformer.

    Automatically detects XSLT version and uses appropriate processor:
    - XSLT 1.0: lxml (fast, native Python)
    - XSLT 2.0/3.0: Saxon (via saxonche)
    """

    # Cache for compiled stylesheets
    _lxml_cache: dict[str, ET.XSLT] = {}
    _saxon_processor: Optional["PySaxonProcessor"] = None

    def __init__(self, mappers_dir: Optional[Path] = None):
        self.mappers_dir = mappers_dir or Path(__file__).parent.parent.parent.parent / "mappers"
        self.mappers_dir.mkdir(parents=True, exist_ok=True)

        # User-uploaded mappers directory
        self.user_mappers_dir = self.mappers_dir / "user_uploads"
        self.user_mappers_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_saxon_processor(cls) -> Optional["PySaxonProcessor"]:
        """Get or create Saxon processor singleton."""
        if not SAXON_AVAILABLE:
            return None
        if cls._saxon_processor is None:
            cls._saxon_processor = PySaxonProcessor(license=False)
        return cls._saxon_processor

    def detect_xslt_version(self, xslt_content: bytes) -> XSLTVersion:
        """
        Detect XSLT version from stylesheet content.

        Looks for version attribute in xsl:stylesheet or xsl:transform element.
        """
        content_str = xslt_content.decode("utf-8", errors="ignore")

        # Look for version="X.X" in stylesheet declaration
        version_match = re.search(
            r'<xsl:(?:stylesheet|transform)[^>]+version\s*=\s*["\'](\d+\.\d+)["\']',
            content_str,
            re.IGNORECASE
        )

        if version_match:
            version = version_match.group(1)
            if version.startswith("3"):
                return XSLTVersion.V3_0
            elif version.startswith("2"):
                return XSLTVersion.V2_0

        return XSLTVersion.V1_0

    def transform(
        self,
        xml_bytes: bytes,
        xslt_bytes: bytes,
        force_version: Optional[XSLTVersion] = None,
        parameters: Optional[dict] = None,
    ) -> TransformResult:
        """
        Transform XML using XSLT.

        Args:
            xml_bytes: Source XML document
            xslt_bytes: XSLT stylesheet
            force_version: Force specific XSLT version (auto-detect if None)
            parameters: Optional XSLT parameters

        Returns:
            TransformResult with output or error
        """
        version = force_version or self.detect_xslt_version(xslt_bytes)

        if version == XSLTVersion.V1_0:
            return self._transform_lxml(xml_bytes, xslt_bytes, parameters)
        else:
            if not SAXON_AVAILABLE:
                return TransformResult(
                    success=False,
                    error=f"XSLT {version.value} requires saxonche. Install with: pip install saxonche",
                    xslt_version=version,
                )
            return self._transform_saxon(xml_bytes, xslt_bytes, version, parameters)

    def transform_with_mapper(
        self,
        xml_bytes: bytes,
        mapper_name: str,
        parameters: Optional[dict] = None,
    ) -> TransformResult:
        """
        Transform XML using a named mapper from the mappers directory.
        """
        # Check built-in mappers first
        mapper_path = self.mappers_dir / mapper_name
        if not mapper_path.exists():
            # Check user uploads
            mapper_path = self.user_mappers_dir / mapper_name
            if not mapper_path.exists():
                return TransformResult(
                    success=False,
                    error=f"Mapper not found: {mapper_name}",
                )

        xslt_bytes = mapper_path.read_bytes()
        return self.transform(xml_bytes, xslt_bytes, parameters=parameters)

    def _transform_lxml(
        self,
        xml_bytes: bytes,
        xslt_bytes: bytes,
        parameters: Optional[dict] = None,
    ) -> TransformResult:
        """Transform using lxml (XSLT 1.0)."""
        try:
            # Cache key based on XSLT content hash
            cache_key = hashlib.md5(xslt_bytes).hexdigest()

            if cache_key not in self._lxml_cache:
                xslt_doc = ET.fromstring(xslt_bytes)
                self._lxml_cache[cache_key] = ET.XSLT(xslt_doc)

            transform = self._lxml_cache[cache_key]
            xml_doc = ET.fromstring(xml_bytes)

            # Apply parameters if provided
            if parameters:
                str_params = {k: ET.XSLT.strparam(str(v)) for k, v in parameters.items()}
                result = transform(xml_doc, **str_params)
            else:
                result = transform(xml_doc)

            output = ET.tostring(result, encoding="utf-8", xml_declaration=True)

            return TransformResult(
                success=True,
                output=output,
                xslt_version=XSLTVersion.V1_0,
                processor="lxml",
            )

        except ET.XMLSyntaxError as e:
            return TransformResult(
                success=False,
                error=f"XML parse error: {e}",
                xslt_version=XSLTVersion.V1_0,
                processor="lxml",
            )
        except ET.XSLTParseError as e:
            return TransformResult(
                success=False,
                error=f"XSLT parse error: {e}",
                xslt_version=XSLTVersion.V1_0,
                processor="lxml",
            )
        except ET.XSLTApplyError as e:
            return TransformResult(
                success=False,
                error=f"XSLT transform error: {e}",
                xslt_version=XSLTVersion.V1_0,
                processor="lxml",
            )

    def _transform_saxon(
        self,
        xml_bytes: bytes,
        xslt_bytes: bytes,
        version: XSLTVersion,
        parameters: Optional[dict] = None,
    ) -> TransformResult:
        """Transform using Saxon (XSLT 2.0/3.0)."""
        proc = self.get_saxon_processor()
        if not proc:
            return TransformResult(
                success=False,
                error="Saxon processor not available",
                xslt_version=version,
            )

        try:
            xslt_proc = proc.new_xslt30_processor()

            # Load XML and XSLT
            xml_node = proc.parse_xml(xml_text=xml_bytes.decode("utf-8"))
            executable = xslt_proc.compile_stylesheet(stylesheet_text=xslt_bytes.decode("utf-8"))

            # Set parameters if provided
            if parameters:
                for key, value in parameters.items():
                    executable.set_parameter(key, proc.make_string_value(str(value)))

            # Transform
            result = executable.transform_to_string(xdm_node=xml_node)

            if result is None:
                # Check for errors
                errors = xslt_proc.error_message if hasattr(xslt_proc, 'error_message') else "Unknown error"
                return TransformResult(
                    success=False,
                    error=f"Saxon transform failed: {errors}",
                    xslt_version=version,
                    processor="saxon",
                )

            return TransformResult(
                success=True,
                output=result.encode("utf-8"),
                xslt_version=version,
                processor="saxon",
            )

        except Exception as e:
            return TransformResult(
                success=False,
                error=f"Saxon error: {e}",
                xslt_version=version,
                processor="saxon",
            )

    def save_user_mapper(self, name: str, content: bytes) -> Path:
        """
        Save a user-uploaded mapper.

        Returns the path where it was saved.
        """
        # Sanitize filename - remove path separators and unsafe chars
        base_name = Path(name).name  # Get just filename, no path
        safe_name = re.sub(r'[^\w\-.]', '_', base_name)
        if not safe_name.endswith(('.xsl', '.xslt')):
            safe_name += '.xsl'

        path = self.user_mappers_dir / safe_name

        # Verify path is within user_mappers_dir (prevent path traversal)
        if not path.resolve().is_relative_to(self.user_mappers_dir.resolve()):
            raise ValueError("Invalid mapper name")

        path.write_bytes(content)
        return path

    def list_mappers(self) -> list[dict]:
        """List all available mappers (built-in and user-uploaded)."""
        mappers = []

        # Built-in mappers
        for xsl_file in self.mappers_dir.glob("*.xsl"):
            if xsl_file.parent == self.mappers_dir:  # Not in subdirectories
                content = xsl_file.read_bytes()
                version = self.detect_xslt_version(content)
                mappers.append({
                    "name": xsl_file.name,
                    "type": "built-in",
                    "xslt_version": version.value,
                    "path": str(xsl_file),
                })

        # User-uploaded mappers
        for xsl_file in self.user_mappers_dir.glob("*.xsl"):
            content = xsl_file.read_bytes()
            version = self.detect_xslt_version(content)
            mappers.append({
                "name": xsl_file.name,
                "type": "user",
                "xslt_version": version.value,
                "path": str(xsl_file),
            })

        return mappers

    def delete_user_mapper(self, name: str) -> bool:
        """Delete a user-uploaded mapper."""
        # Sanitize - use only the base filename
        safe_name = Path(name).name
        path = self.user_mappers_dir / safe_name

        # Verify path is within user_mappers_dir and exists
        resolved = path.resolve()
        if (resolved.is_relative_to(self.user_mappers_dir.resolve())
                and path.exists()
                and path.is_file()):
            path.unlink()
            return True
        return False

    @staticmethod
    def is_saxon_available() -> bool:
        """Check if Saxon is available for XSLT 2.0/3.0."""
        return SAXON_AVAILABLE


# Singleton instance
_transformer: Optional[TransformerService] = None


def get_transformer() -> TransformerService:
    """Get or create transformer service singleton."""
    global _transformer
    if _transformer is None:
        _transformer = TransformerService()
    return _transformer
