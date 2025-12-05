"""
Rules Sync Service - Downloads and maintains validation schemas and rules.

Sources:
- UBL XSD: OASIS UBL 2.1
- Peppol BIS: OpenPeppol/peppol-bis-invoice-3
- EN 16931: ConnectingEurope/eInvoicing-EN16931
- phive-rules: phax/phive-rules (complete validation rule sets)
"""
import json
import logging
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

# Base directories from config
BASE_DIR = settings.base_dir
SCHEMAS_DIR = settings.schemas_dir
XSD_DIR = settings.xsd_dir
SCHEMATRON_DIR = settings.schematron_dir
RULES_DIR = settings.rules_dir

# Download sources
SOURCES = {
    "ubl": {
        "name": "UBL 2.1 XSD Schemas",
        "url": "https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip",
        "type": "xsd",
        "extract_path": "xsd/maindoc",
    },
    "peppol-bis": {
        "name": "Peppol BIS 3.0 Schematron",
        "url": "https://github.com/OpenPeppol/peppol-bis-invoice-3/archive/refs/heads/master.zip",
        "type": "schematron",
        "github_repo": "OpenPeppol/peppol-bis-invoice-3",
    },
    "en16931-ubl": {
        "name": "EN 16931 UBL Validation",
        "url": "https://github.com/ConnectingEurope/eInvoicing-EN16931/archive/refs/heads/master.zip",
        "type": "schematron",
        "github_repo": "ConnectingEurope/eInvoicing-EN16931",
    },
}


@dataclass
class SyncStatus:
    source: str
    name: str
    last_sync: Optional[datetime]
    files_count: int
    status: str  # "synced", "pending", "error"
    error: Optional[str] = None


class RulesSyncService:
    """Service to download and maintain validation rules."""

    def __init__(self):
        # Ensure directories exist
        XSD_DIR.mkdir(parents=True, exist_ok=True)
        SCHEMATRON_DIR.mkdir(parents=True, exist_ok=True)
        RULES_DIR.mkdir(parents=True, exist_ok=True)

        self.status_file = SCHEMAS_DIR / "sync_status.json"

    def get_status(self) -> dict:
        """Get sync status for all sources."""
        status = self._load_status()

        result = {
            "sources": [],
            "xsd_schemas": self._count_files(XSD_DIR, "*.xsd"),
            "schematron_rules": self._count_files(SCHEMATRON_DIR, "*.xslt") + self._count_files(SCHEMATRON_DIR, "*.sch"),
        }

        for source_id, source_info in SOURCES.items():
            source_status = status.get(source_id, {})
            result["sources"].append({
                "id": source_id,
                "name": source_info["name"],
                "type": source_info["type"],
                "last_sync": source_status.get("last_sync"),
                "status": source_status.get("status", "pending"),
                "error": source_status.get("error"),
            })

        return result

    def sync_all(self) -> dict:
        """Sync all rule sources."""
        results = {}
        for source_id in SOURCES:
            results[source_id] = self.sync_source(source_id)
        return results

    def sync_source(self, source_id: str) -> dict:
        """Sync a specific source."""
        if source_id not in SOURCES:
            return {"success": False, "error": f"Unknown source: {source_id}"}

        source = SOURCES[source_id]
        logger.info(f"Syncing {source['name']}...")

        try:
            if source_id == "ubl":
                result = self._sync_ubl()
            elif source_id == "peppol-bis":
                result = self._sync_peppol_bis()
            elif source_id == "en16931-ubl":
                result = self._sync_en16931()
            else:
                result = {"success": False, "error": "Sync not implemented"}

            # Update status
            self._update_status(source_id, "synced" if result["success"] else "error", result.get("error"))
            return result

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Failed to sync {source_id}")
            self._update_status(source_id, "error", error_msg)
            return {"success": False, "error": error_msg}

    def _sync_ubl(self) -> dict:
        """Download UBL 2.1 XSD schemas."""
        url = SOURCES["ubl"]["url"]
        temp_zip = SCHEMAS_DIR / "ubl_temp.zip"
        temp_dir = SCHEMAS_DIR / "ubl_temp"

        try:
            # Download
            logger.info(f"Downloading UBL schemas from {url}")
            urllib.request.urlretrieve(url, temp_zip)

            # Extract
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(temp_dir)

            # Find and copy XSD files
            copied = 0
            for xsd_dir in temp_dir.rglob("xsd"):
                if xsd_dir.is_dir():
                    # Copy maindoc schemas
                    maindoc = xsd_dir / "maindoc"
                    if maindoc.exists():
                        for xsd in maindoc.glob("*.xsd"):
                            shutil.copy(xsd, XSD_DIR / xsd.name)
                            copied += 1

                    # Copy common schemas
                    common_src = xsd_dir / "common"
                    common_dest = XSD_DIR / "common"
                    if common_src.exists():
                        if common_dest.exists():
                            shutil.rmtree(common_dest)
                        shutil.copytree(common_src, common_dest)
                        copied += len(list(common_src.glob("*.xsd")))

            return {"success": True, "files_copied": copied}

        finally:
            # Cleanup
            if temp_zip.exists():
                temp_zip.unlink()
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _sync_peppol_bis(self) -> dict:
        """Download Peppol BIS 3.0 schematron rules."""
        url = SOURCES["peppol-bis"]["url"]
        temp_zip = SCHEMAS_DIR / "peppol_temp.zip"
        temp_dir = SCHEMAS_DIR / "peppol_temp"

        try:
            # Download
            logger.info(f"Downloading Peppol BIS rules from {url}")
            urllib.request.urlretrieve(url, temp_zip)

            # Extract
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(temp_dir)

            # Find and copy schematron files
            peppol_dir = SCHEMATRON_DIR / "peppol-bis3"
            peppol_dir.mkdir(exist_ok=True)

            copied = 0
            for root_dir in temp_dir.iterdir():
                if root_dir.is_dir():
                    # Look for compiled XSLT in rules directory
                    rules_dir = root_dir / "rules"
                    if rules_dir.exists():
                        for sch_dir in rules_dir.iterdir():
                            if sch_dir.is_dir():
                                output_dir = sch_dir / "output"
                                if output_dir.exists():
                                    for xslt in output_dir.glob("*.xslt"):
                                        dest = peppol_dir / xslt.name
                                        shutil.copy(xslt, dest)
                                        copied += 1

                    # Also look for .sch files
                    for sch in root_dir.rglob("*.sch"):
                        dest = peppol_dir / sch.name
                        if not dest.exists():
                            shutil.copy(sch, dest)
                            copied += 1

            return {"success": True, "files_copied": copied}

        finally:
            if temp_zip.exists():
                temp_zip.unlink()
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _sync_en16931(self) -> dict:
        """Download EN 16931 validation rules."""
        url = SOURCES["en16931-ubl"]["url"]
        temp_zip = SCHEMAS_DIR / "en16931_temp.zip"
        temp_dir = SCHEMAS_DIR / "en16931_temp"

        try:
            # Download
            logger.info(f"Downloading EN 16931 rules from {url}")
            urllib.request.urlretrieve(url, temp_zip)

            # Extract
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(temp_dir)

            # Find and copy schematron/xslt files
            en16931_dir = SCHEMATRON_DIR / "en16931"
            en16931_dir.mkdir(exist_ok=True)

            copied = 0
            for root_dir in temp_dir.iterdir():
                if root_dir.is_dir():
                    # UBL validation
                    ubl_xslt = root_dir / "ubl" / "xslt"
                    if ubl_xslt.exists():
                        for xslt in ubl_xslt.glob("*.xslt"):
                            dest = en16931_dir / f"ubl_{xslt.name}"
                            shutil.copy(xslt, dest)
                            copied += 1

                    # CII validation
                    cii_xslt = root_dir / "cii" / "xslt"
                    if cii_xslt.exists():
                        for xslt in cii_xslt.glob("*.xslt"):
                            dest = en16931_dir / f"cii_{xslt.name}"
                            shutil.copy(xslt, dest)
                            copied += 1

                    # Also copy .sch files
                    for sch in root_dir.rglob("*.sch"):
                        dest = en16931_dir / sch.name
                        if not dest.exists():
                            shutil.copy(sch, dest)
                            copied += 1

            return {"success": True, "files_copied": copied}

        finally:
            if temp_zip.exists():
                temp_zip.unlink()
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _load_status(self) -> dict:
        """Load sync status from file."""
        if self.status_file.exists():
            return json.loads(self.status_file.read_text())
        return {}

    def _update_status(self, source_id: str, status: str, error: Optional[str] = None):
        """Update sync status for a source."""
        all_status = self._load_status()
        all_status[source_id] = {
            "last_sync": datetime.now().isoformat(),
            "status": status,
            "error": error,
        }
        self.status_file.write_text(json.dumps(all_status, indent=2))

    def _count_files(self, directory: Path, pattern: str) -> int:
        """Count files matching pattern in directory."""
        if not directory.exists():
            return 0
        return len(list(directory.rglob(pattern)))


# Singleton
_service: Optional[RulesSyncService] = None


def get_rules_sync_service() -> RulesSyncService:
    """Get or create rules sync service singleton."""
    global _service
    if _service is None:
        _service = RulesSyncService()
    return _service
