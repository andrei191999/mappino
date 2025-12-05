#!/usr/bin/env python3
"""Download UBL 2.1 XSD schemas from OASIS."""

import urllib.request
import zipfile
import shutil
from pathlib import Path

UBL_URL = "https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip"
SCRIPT_DIR = Path(__file__).parent


def download_ubl_schemas():
    """Download and extract UBL 2.1 schemas."""
    zip_path = SCRIPT_DIR / "ubl.zip"
    temp_dir = SCRIPT_DIR / "ubl-temp"

    print(f"Downloading UBL 2.1 schemas from {UBL_URL}...")
    urllib.request.urlretrieve(UBL_URL, zip_path)

    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)

    # Find the xsd directory (might be nested)
    xsd_source = None
    for path in temp_dir.rglob("xsd"):
        if path.is_dir() and (path / "maindoc").exists():
            xsd_source = path
            break

    if not xsd_source:
        print("ERROR: Could not find xsd/maindoc in archive")
        return False

    # Copy main document schemas
    maindoc = xsd_source / "maindoc"
    for xsd in maindoc.glob("*.xsd"):
        dest = SCRIPT_DIR / xsd.name
        shutil.copy(xsd, dest)
        print(f"  Copied {xsd.name}")

    # Copy common schemas
    common_src = xsd_source / "common"
    common_dest = SCRIPT_DIR / "common"
    if common_src.exists():
        if common_dest.exists():
            shutil.rmtree(common_dest)
        shutil.copytree(common_src, common_dest)
        print(f"  Copied common/ directory")

    # Cleanup
    zip_path.unlink()
    shutil.rmtree(temp_dir)

    print("\nDone! UBL 2.1 schemas installed.")
    return True


if __name__ == "__main__":
    download_ubl_schemas()
