"""
Application configuration using pydantic-settings.

All configuration values can be set via environment variables or .env file.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    All settings can be overridden via environment variables.
    Prefix: none (use exact names)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # Application
    # ===========================================
    app_name: str = "Peppol Tools API"
    app_version: str = "1.0.0"
    app_description: str = "XML transformation, validation, and Peppol lookup services"
    debug: bool = False
    log_level: str = "INFO"

    # ===========================================
    # CORS
    # ===========================================
    cors_origins: list[str] = Field(default=["*"])
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # ===========================================
    # Rate Limiting
    # ===========================================
    rate_limit_validation: str = "10/minute"
    rate_limit_lookup: str = "30/minute"

    # ===========================================
    # Peppol Directory / Lookup
    # ===========================================
    peppol_directory_base: str = "https://directory.peppol.eu"
    helger_api_base: str = "https://peppol.helger.com/api"
    helger_wsdl_url: str = "https://peppol.helger.com/wsdvs?wsdl"
    helger_endpoint: str = "https://peppol.helger.com/wsdvs"
    helger_rate_limit_ms: int = 550

    # SML environments
    sml_production: str = "digitprod"
    sml_test: str = "digittest"
    use_test_sml: bool = False

    # Lookup defaults
    lookup_fallback_icds: list[str] = Field(default=["0106", "0199", "0060"])
    lookup_max_retries: int = 5
    lookup_base_backoff: float = 0.5

    # ===========================================
    # File Paths (relative to project root)
    # ===========================================
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)

    @property
    def schemas_dir(self) -> Path:
        return self.base_dir / "schemas"

    @property
    def xsd_dir(self) -> Path:
        return self.schemas_dir / "xsd"

    @property
    def schematron_dir(self) -> Path:
        return self.schemas_dir / "schematron"

    @property
    def rules_dir(self) -> Path:
        return self.schemas_dir / "rules"

    @property
    def mappers_dir(self) -> Path:
        return self.base_dir / "mappers"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def codelists_dir(self) -> Path:
        return self.data_dir / "codelists"

    # ===========================================
    # Schema Sync Sources (can override URLs)
    # ===========================================
    ubl_schema_url: str = "https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip"
    peppol_bis_url: str = "https://github.com/OpenPeppol/peppol-bis-invoice-3/archive/refs/heads/master.zip"
    en16931_url: str = "https://github.com/ConnectingEurope/eInvoicing-EN16931/archive/refs/heads/master.zip"
    peppol_codelists_url: str = "https://docs.peppol.eu/edelivery/codelists/"

    # ===========================================
    # Firebase (optional)
    # ===========================================
    firebase_enabled: bool = False
    firebase_project_id: Optional[str] = None
    firebase_credentials_path: Optional[str] = None
    firebase_database_url: Optional[str] = None  # For Realtime Database (optional)

    # When running in GCP, credentials are auto-detected
    # Set this to use a specific service account
    google_application_credentials: Optional[str] = None

    # ===========================================
    # GCP Secret Manager (optional)
    # ===========================================
    gcp_project_id: Optional[str] = None
    use_secret_manager: bool = False
    secret_cache_ttl_minutes: int = 5

    # ===========================================
    # Logging Configuration
    # ===========================================
    enable_cloud_logging: bool = False
    log_format: str = "json"  # "json" or "console"
    enable_request_logging: bool = True

    # ===========================================
    # Feature Flags
    # ===========================================
    enable_helger_validator: bool = True
    enable_xsd_validator: bool = True
    enable_schematron_validator: bool = True
    enable_legacy_routes: bool = True  # /api/lookup, /api/validation without v1

    # ===========================================
    # File Upload Limits
    # ===========================================
    max_upload_size_mb: int = 50
    max_xml_size_mb: int = 10
    max_xslt_size_mb: int = 5


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are loaded once and cached for performance.
    To reload settings (e.g., in tests), clear the cache:
        get_settings.cache_clear()
    """
    return Settings()


# Convenience function to get settings
settings = get_settings()
