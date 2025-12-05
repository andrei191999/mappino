"""
Peppol Code List Service - Auto-sync from OpenPeppol
Fetches participant identifier schemes (ICDs) from official source.
"""
import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from ..config import settings

CODELISTS_BASE = "https://docs.peppol.eu/edelivery/codelists"
CACHE_DIR = settings.codelists_dir
CACHE_TTL_HOURS = 24  # Refresh once per day


class CodeListService:
    _instance: Optional["CodeListService"] = None
    _schemes: list[dict] = []
    _last_fetch: Optional[datetime] = None
    _version: str = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._schemes:
            self._load_or_fetch()

    def _load_or_fetch(self):
        """Load from cache or fetch fresh"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / "participant_schemes.json"
        meta_file = CACHE_DIR / "meta.json"

        # Check cache validity
        if cache_file.exists() and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                last_fetch = datetime.fromisoformat(meta.get("last_fetch", "2000-01-01"))
                if datetime.now() - last_fetch < timedelta(hours=CACHE_TTL_HOURS):
                    self._schemes = json.loads(cache_file.read_text(encoding="utf-8"))
                    self._version = meta.get("version", "")
                    self._last_fetch = last_fetch
                    return
            except Exception:
                pass

        # Fetch fresh
        self._fetch_and_cache()

    def _fetch_and_cache(self):
        """Fetch latest from OpenPeppol"""
        try:
            # First get the index page to find latest version
            index_resp = requests.get(CODELISTS_BASE, timeout=30)
            index_resp.raise_for_status()

            # Extract version from page (look for "v9.4" pattern)
            version_match = re.search(r'v(\d+\.\d+)', index_resp.text)
            version = version_match.group(1) if version_match else "9.4"

            # Fetch the JSON
            url = f"{CODELISTS_BASE}/v{version}/Peppol%20Code%20Lists%20-%20Participant%20identifier%20schemes%20v{version}.json"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            self._schemes = data.get("values", [])
            self._version = data.get("version", version)
            self._last_fetch = datetime.now()

            # Cache it
            cache_file = CACHE_DIR / "participant_schemes.json"
            meta_file = CACHE_DIR / "meta.json"
            cache_file.write_text(json.dumps(self._schemes, indent=2), encoding="utf-8")
            meta_file.write_text(json.dumps({
                "version": self._version,
                "last_fetch": self._last_fetch.isoformat(),
                "source": url,
            }), encoding="utf-8")

        except Exception as e:
            # If fetch fails, try to load from cache anyway
            cache_file = CACHE_DIR / "participant_schemes.json"
            if cache_file.exists():
                self._schemes = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                # Fallback to hardcoded minimal list
                self._schemes = self._get_fallback_schemes()

    def _get_fallback_schemes(self) -> list[dict]:
        """Minimal fallback if everything fails"""
        return [
            {"iso6523": "0002", "schemeid": "FR:SIRENE", "country": "FR", "scheme-name": "SIRENE", "state": "active"},
            {"iso6523": "0007", "schemeid": "SE:ORGNR", "country": "SE", "scheme-name": "Organisationsnummer", "state": "active"},
            {"iso6523": "0060", "schemeid": "DUNS", "country": "international", "scheme-name": "DUNS Number", "state": "active"},
            {"iso6523": "0088", "schemeid": "GLN", "country": "international", "scheme-name": "Global Location Number", "state": "active"},
            {"iso6523": "0106", "schemeid": "NL:KVK", "country": "NL", "scheme-name": "KvK Number", "state": "active"},
            {"iso6523": "0190", "schemeid": "NL:OINO", "country": "NL", "scheme-name": "OIN", "state": "active"},
            {"iso6523": "0184", "schemeid": "DK:CVR", "country": "DK", "scheme-name": "CVR Number", "state": "active"},
            {"iso6523": "0208", "schemeid": "BE:EN", "country": "BE", "scheme-name": "Enterprise Number", "state": "active"},
            {"iso6523": "9906", "schemeid": "IT:IVA", "country": "IT", "scheme-name": "VAT Number", "state": "active"},
            {"iso6523": "9930", "schemeid": "DE:VAT", "country": "DE", "scheme-name": "VAT Number", "state": "active"},
        ]

    def force_refresh(self) -> dict:
        """Force refresh from OpenPeppol"""
        self._fetch_and_cache()
        return self.get_status()

    def get_status(self) -> dict:
        """Get sync status"""
        return {
            "version": self._version,
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "scheme_count": len(self._schemes),
            "active_count": len([s for s in self._schemes if s.get("state") == "active"]),
        }

    def get_all_schemes(self, include_inactive: bool = False) -> list[dict]:
        """Get all schemes, optionally including deprecated/removed"""
        if include_inactive:
            return self._schemes
        return [s for s in self._schemes if s.get("state") == "active"]

    def get_scheme_by_icd(self, icd: str) -> Optional[dict]:
        """Get scheme by ICD code (e.g., '0208')"""
        for s in self._schemes:
            if s.get("iso6523") == icd:
                return s
        return None

    def get_schemes_by_country(self, country: str) -> list[dict]:
        """Get schemes for a specific country"""
        country = country.upper()
        return [s for s in self._schemes
                if s.get("country", "").upper() == country and s.get("state") == "active"]

    def validate_identifier(self, icd: str, identifier: str) -> dict:
        """Validate identifier against scheme's regex rules"""
        scheme = self.get_scheme_by_icd(icd)
        if not scheme:
            return {"valid": False, "error": f"Unknown ICD: {icd}"}

        rules = scheme.get("validation-rules", "")
        if not rules:
            return {"valid": True, "warning": "No validation rules defined"}

        # Extract regex from rules
        regex_match = re.search(r'RegEx:\s*([^\n]+)', rules)
        if not regex_match:
            return {"valid": True, "warning": "No regex pattern found"}

        pattern = regex_match.group(1).strip()
        try:
            if re.fullmatch(pattern, identifier):
                return {"valid": True, "pattern": pattern}
            else:
                return {"valid": False, "error": f"Does not match pattern: {pattern}"}
        except re.error as e:
            return {"valid": True, "warning": f"Invalid regex in scheme: {e}"}

    def search_schemes(self, query: str) -> list[dict]:
        """Search schemes by name, country, or ICD"""
        query = query.lower()
        results = []
        for s in self._schemes:
            if s.get("state") != "active":
                continue
            if (query in s.get("iso6523", "").lower() or
                query in s.get("schemeid", "").lower() or
                query in s.get("country", "").lower() or
                query in s.get("scheme-name", "").lower()):
                results.append(s)
        return results
