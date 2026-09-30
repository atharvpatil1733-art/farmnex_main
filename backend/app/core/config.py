from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.

    Values are loaded from environment variables / .env.
    Production-specific validation is performed here so that
    insecure configuration fails fast during application startup.
    """

    # ============================================================
    # APPLICATION
    # ============================================================

    app_name: str = "FarmNex API"
    app_version: str = "1.0.0"

    environment: Literal[
        "development",
        "testing",
        "staging",
        "production",
    ] = "development"

    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    
    
    
    public_registration_roles: list[str] = Field(
        default=["FARMER", "BUYER", "VENDOR"],
        min_length=1,
    )

    # ============================================================
    # DATABASE
    # ============================================================

    database_url: str

    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_pool_recycle: int = Field(default=1800, ge=60)
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    # ============================================================
    # SUPABASE STORAGE
    # ============================================================

    storage_provider: Literal["supabase"] = "supabase"

    storage_bucket: str = Field(
        min_length=1,
        max_length=100,
    )

    supabase_url: str = Field(
        min_length=1,
    )

    supabase_secret_key: SecretStr = Field(
        min_length=1,
    )

    storage_signed_url_expire_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
    )

    storage_max_upload_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        le=10 * 1024 * 1024,
    )

    storage_test_endpoints_enabled: bool = False

    storage_timeout_seconds: float = Field(
        default=15.0,
        ge=3.0,
        le=60.0,
    )

    # ============================================================
    # REDIS
    # ============================================================

    redis_url: str | None = None
    redis_enabled: bool = False

    redis_max_connections: int = Field(
        default=20,
        ge=1,
    )

    redis_socket_timeout: int = Field(
        default=5,
        ge=1,
    )

    redis_socket_connect_timeout: int = Field(
        default=5,
        ge=1,
    )

    # ============================================================
    # JWT
    # ============================================================

    jwt_algorithm: Literal[
        "RS256",
        "RS384",
        "RS512",
    ] = "RS256"

    jwt_issuer: str = "farmnex-api"
    jwt_audience: str = "farmnex-mobile"

    access_token_expire_minutes: int = Field(
        default=1440,
        ge=5,
        le=1440,
    )
    refresh_token_expire_days: int = Field(
        default=90,
        ge=1,
        le=180,
    )

    registration_token_expire_minutes: int = Field(
        default=10,
        ge=1,
        le=180,
    )

    jwt_private_key_path: str = "secrets/jwt_private.pem"
    jwt_public_key_path: str = "secrets/jwt_public.pem"

    # ============================================================
    # PASSWORD SECURITY
    # ============================================================

    password_hash_algorithm: Literal["argon2id"] = "argon2id"

    # ============================================================
    # SESSION SECURITY
    # ============================================================

    session_expire_days: int = Field(
        default=90,
        ge=1,
        le=90,
    )

    refresh_token_rotation_enabled: bool = True
    refresh_token_reuse_detection_enabled: bool = True

    max_sessions_per_user: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    # ============================================================
    # CORS
    # ============================================================

    cors_origins: str = "*"

    cors_allow_credentials: bool = False

    # ============================================================
    # SECURITY
    # ============================================================

    enable_security_headers: bool = True

    secure_cookies: bool = True

    trust_proxy_headers: bool = False

    # ============================================================
    # AUDIT LOGGING
    # ============================================================

    audit_log_enabled: bool = True

    # ============================================================
    # SENTRY
    # ============================================================

    sentry_enabled: bool = False

    sentry_dsn: str | None = None

    sentry_environment: str = "development"

    sentry_traces_sample_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    # ============================================================
    # EMAIL
    # ============================================================

    email_enabled: bool = False

    smtp_host: str | None = None

    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
    )

    smtp_username: str | None = None

    smtp_password: str | None = None

    smtp_use_tls: bool = True

    email_from: str | None = None

    email_from_name: str = "FarmNex"

    # ============================================================
    # OTP
    # ============================================================

    otp_enabled: bool = True

    otp_length: int = Field(
        default=6,
        ge=6,
        le=6,
    )

    otp_expire_minutes: int = Field(
        default=5,
        ge=1,
        le=30,
    )

    otp_max_attempts: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    otp_provider: Literal[
        "minimoth",
    ] = "minimoth"

    otp_resend_cooldown_seconds: int = Field(
        default=60,
        ge=30,
        le=300,
    )

    otp_max_resends: int = Field(
        default=3,
        ge=1,
        le=10,
    )

    minimoth_api_base_url: str = (
        "https://api.minimoth.dev"
    )

    minimoth_api_key: str | None = None

    minimoth_timeout_seconds: float = Field(
        default=10.0,
        ge=3.0,
        le=30.0,
    )

    # ============================================================
    # EXTERNAL APIs
    # ============================================================

    weather_api_enabled: bool = False

    weather_api_base_url: str | None = None
    weather_api_key: str | None = None

    weather_api_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
    )

    market_api_enabled: bool = False

    market_api_base_url: str | None = None
    market_api_key: str | None = None

    market_api_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
    )

    notification_enabled: bool = False

    notification_api_base_url: str | None = None
    notification_api_key: str | None = None

    notification_api_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
    )

    # ============================================================
    # API DOCUMENTATION
    # ============================================================

    enable_openapi: bool = True
    enable_swagger: bool = True
    enable_redoc: bool = True

    # ============================================================
    # FEATURE FLAGS
    # ============================================================

    enable_registration: bool = True
    enable_email_verification: bool = False
    enable_otp_login: bool = True
    enable_file_uploads: bool = True

    # ============================================================
    # PYDANTIC SETTINGS CONFIG
    # ============================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================
    # VALIDATORS
    # ============================================================

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip()

        if not value.startswith("/"):
            raise ValueError(
                "API prefix must start with '/'."
            )

        return value.rstrip("/") or "/"

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        return value.strip()

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")

        if not value.startswith("https://"):
            raise ValueError(
                "SUPABASE_URL must use HTTPS."
            )

        return value

    @field_validator("storage_bucket")
    @classmethod
    def validate_storage_bucket(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "STORAGE_BUCKET cannot be empty."
            )

        if "/" in value or "\\" in value:
            raise ValueError(
                "STORAGE_BUCKET must be a bucket name, not a path."
            )

        return value

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        """
        Enforce additional security requirements based on
        the deployment environment.
        """

        # --------------------------------------------------------
        # Supabase Storage
        # --------------------------------------------------------

        if self.storage_provider != "supabase":
            raise ValueError("STORAGE_PROVIDER must be supabase.")

        if not self.supabase_url.strip():
            raise ValueError("SUPABASE_URL is required for storage.")

        if not self.supabase_secret_key.get_secret_value().strip():
            raise ValueError("SUPABASE_SECRET_KEY is required for storage.")

        if not self.storage_bucket.strip():
            raise ValueError("STORAGE_BUCKET is required for storage.")

        # --------------------------------------------------------
        # Production security
        # --------------------------------------------------------

        if self.environment == "production":

            if self.debug:
                raise ValueError(
                    "DEBUG must be false in production."
                )

            if not self.secure_cookies:
                raise ValueError(
                    "SECURE_COOKIES must be true in production."
                )

            if not self.enable_security_headers:
                raise ValueError(
                    "Security headers must be enabled in production."
                )

            if self.trust_proxy_headers:
                raise ValueError(
                    "TRUST_PROXY_HEADERS must be explicitly reviewed "
                    "before enabling it in production."
                )

            if self.db_echo:
                raise ValueError(
                    "DB_ECHO must be false in production."
                )



            if not self.audit_log_enabled:
                raise ValueError(
                    "Audit logging must be enabled in production."
                )

            if self.jwt_algorithm not in {
                "RS256",
                "RS384",
                "RS512",
            }:
                raise ValueError(
                    "Production must use an approved asymmetric JWT algorithm."
                )

            if not self.jwt_private_key_path:
                raise ValueError(
                    "JWT private key path is required in production."
                )

            if not self.jwt_public_key_path:
                raise ValueError(
                    "JWT public key path is required in production."
                )

        # --------------------------------------------------------
        # Redis
        # --------------------------------------------------------

        if self.redis_enabled and not self.redis_url:
            raise ValueError(
                "REDIS_URL is required when Redis is enabled."
            )

        # --------------------------------------------------------
        # Sentry
        # --------------------------------------------------------

        if self.sentry_enabled and not self.sentry_dsn:
            raise ValueError(
                "SENTRY_DSN is required when Sentry is enabled."
            )

        # --------------------------------------------------------
        # Session / refresh-token policy
        # --------------------------------------------------------

        if self.session_expire_days != self.refresh_token_expire_days:
            raise ValueError(
                "SESSION_EXPIRE_DAYS must match "
                "REFRESH_TOKEN_EXPIRE_DAYS."
            )

        # --------------------------------------------------------
        # Email
        # --------------------------------------------------------

        if self.email_enabled:
            required_email_values = {
                "SMTP_HOST": self.smtp_host,
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password,
                "EMAIL_FROM": self.email_from,
            }

            missing = [
                name
                for name, value in required_email_values.items()
                if not value
            ]

            if missing:
                raise ValueError(
                    "Missing email configuration: "
                    + ", ".join(missing)
                )

        # --------------------------------------------------------
        # OTP
        # --------------------------------------------------------

        if self.enable_otp_login and not self.otp_enabled:
            raise ValueError(
                "ENABLE_OTP_LOGIN requires OTP_ENABLED=true."
            )

        if self.otp_enabled and self.otp_provider == "minimoth":
            if not self.minimoth_api_key:
                raise ValueError(
                    "MINIMOTH_API_KEY is required when "
                    "OTP_PROVIDER=minimoth and "
                    "OTP_ENABLED=true."
                )

        # --------------------------------------------------------
        # External APIs
        # --------------------------------------------------------

        if self.weather_api_enabled:
            if not self.weather_api_base_url:
                raise ValueError(
                    "WEATHER_API_BASE_URL is required when "
                    "weather API is enabled."
                )

            if not self.weather_api_key:
                raise ValueError(
                    "WEATHER_API_KEY is required when "
                    "weather API is enabled."
                )

        if self.market_api_enabled:
            if not self.market_api_base_url:
                raise ValueError(
                    "MARKET_API_BASE_URL is required when "
                    "market API is enabled."
                )

            if not self.market_api_key:
                raise ValueError(
                    "MARKET_API_KEY is required when "
                    "market API is enabled."
                )

        if self.notification_enabled:
            if not self.notification_api_base_url:
                raise ValueError(
                    "NOTIFICATION_API_BASE_URL is required when "
                    "notifications are enabled."
                )

            if not self.notification_api_key:
                raise ValueError(
                    "NOTIFICATION_API_KEY is required when "
                    "notifications are enabled."
                )

        return self


# ================================================================
# SINGLETON SETTINGS INSTANCE
# ================================================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the application settings singleton.

    @lru_cache ensures the .env file and environment variables
    are parsed only once during the application's lifetime.
    """
    return Settings()


settings = get_settings()