"""
Peppol lookup service - wraps logic from peppol_lookup.py
"""
import re
import time
import random
from urllib.parse import quote
import requests

PD_BASE = "https://directory.peppol.eu"
HELGER_BASE = "https://peppol.helger.com/api"
SML_PROD = "digitprod"
SML_TEST = "digittest"
ISO6523_PREFIX = "iso6523-actorid-upis::"

DEFAULT_FALLBACK_ICDS = ["0106", "0199", "0060"]
MAX_TRIES = 5
BASE_BACKOFF = 0.5


class LookupService:
    def __init__(
        self,
        fallback_icds: list[str] | None = None,
        use_test_sml: bool = False,
        merge_pd_discovery: bool = True,
    ):
        self.fallback_icds = fallback_icds or DEFAULT_FALLBACK_ICDS
        self.sml = SML_TEST if use_test_sml else SML_PROD
        self.merge_pd = merge_pd_discovery
        self._session = requests.Session()
        self._cache: dict[str, dict] = {}

    def _get_json(self, url: str, timeout: int = 30) -> dict:
        if url in self._cache:
            return self._cache[url]
        for attempt in range(1, MAX_TRIES + 1):
            resp = self._session.get(url, timeout=timeout)
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                wait = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            self._cache[url] = data
            return data
        resp.raise_for_status()
        return {}

    def _normalize_be(self, raw: str) -> str | None:
        s = raw.upper().strip()
        if s.startswith("BE"):
            s = s[2:]
        digits = "".join(c for c in s if c.isdigit())
        if len(digits) == 9:
            digits = "0" + digits
        if len(digits) == 10:
            return f"0208:{digits}"
        return None

    def _normalize_gln(self, raw: str) -> str | None:
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) == 13:
            return f"0088:{digits}"
        return None

    def _normalize_iso6523(self, raw: str) -> str | None:
        s = raw.strip()
        if s.startswith(ISO6523_PREFIX):
            return s[len(ISO6523_PREFIX):]
        if re.fullmatch(r"\d{4}:.+", s):
            return s
        return None

    def _build_candidates(self, raw: str) -> list[str]:
        cands = []
        raw_stripped = raw.strip()

        # Already normalized
        if v := self._normalize_iso6523(raw_stripped):
            if v not in cands:
                cands.append(v)

        # GLN
        if v := self._normalize_gln(raw_stripped):
            if v not in cands:
                cands.append(v)

        # Belgian
        s = raw_stripped.upper()
        if s.startswith("BE") or (len("".join(c for c in s if c.isdigit())) in (9, 10)):
            if v := self._normalize_be(raw_stripped):
                if v not in cands:
                    cands.append(v)

        # Fallback ICDs
        raw_clean = re.sub(r"\s+", "", raw_stripped).upper()
        for icd in self.fallback_icds:
            v = f"{icd}:{raw_clean}"
            if v not in cands:
                cands.append(v)

        return cands

    def _pd_search(self, raw: str, limit: int = 10) -> list[str]:
        url = f"{PD_BASE}/search/1.0/json?q={quote(raw)}&rpc={limit}"
        try:
            data = self._get_json(url)
            out = set()
            for m in data.get("match", []):
                pid = m.get("participantID")
                if isinstance(pid, dict) and pid.get("scheme") == "iso6523-actorid-upis":
                    out.add(pid.get("value", ""))
                elif isinstance(pid, str) and pid.startswith(ISO6523_PREFIX):
                    out.add(pid[len(ISO6523_PREFIX):])
            return list(out)
        except Exception:
            return []

    def _check_registered(self, icd_value: str) -> dict:
        url = f"{HELGER_BASE}/ppidexistence/{self.sml}/{quote(ISO6523_PREFIX + icd_value, safe='')}"
        j = self._get_json(url)
        return {"exists": bool(j.get("exists")), "smpHostURI": j.get("smpHostURI")}

    def _get_smp_meta(self, icd_value: str) -> dict:
        url = f"{HELGER_BASE}/smpquery/{self.sml}/{quote(ISO6523_PREFIX + icd_value, safe='')}?businessCard=true"
        return self._get_json(url)

    def lookup(self, raw: str) -> list[dict]:
        rows = []
        tried = set()
        candidates = self._build_candidates(raw)

        if self.merge_pd:
            for c in self._pd_search(raw, limit=10):
                if c not in candidates:
                    candidates.append(c)

        if not candidates:
            return [{"input": raw, "participant": "", "registered": False,
                     "business_name": "", "country": "", "doc_types": 0, "error": "no_candidates"}]

        for icd_value in candidates:
            if icd_value in tried:
                continue
            tried.add(icd_value)

            try:
                reg = self._check_registered(icd_value)
            except Exception as e:
                rows.append({"input": raw, "participant": icd_value, "registered": "error",
                             "business_name": "", "country": "", "doc_types": 0, "error": str(e)})
                continue

            if not reg.get("exists"):
                rows.append({"input": raw, "participant": icd_value, "registered": False,
                             "business_name": "", "country": "", "doc_types": 0, "error": ""})
                continue

            # Get business card info
            bc_name, bc_country, doc_count = "", "", 0
            try:
                meta = self._get_smp_meta(icd_value)
                urls = meta.get("urls", []) or []
                doc_count = len(urls)
                bc = meta.get("businessCard", {})
                ents = bc.get("entity", [])
                if ents:
                    names = ents[0].get("name", [])
                    if names:
                        bc_name = names[0].get("name", "")
                    bc_country = ents[0].get("countrycode", "")
            except Exception:
                pass

            rows.append({
                "input": raw,
                "participant": icd_value,
                "registered": True,
                "business_name": bc_name,
                "country": bc_country,
                "doc_types": doc_count,
                "error": "",
            })
            time.sleep(0.3)  # rate limit

        return rows
