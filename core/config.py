"""
Configuration Management — Production Environment Setup

Loads and validates environment variables for production deployment.
Supports local development (.env file) and remote deployment (Render, Heroku, etc.)

Environment Variables:
  DEPLOYMENT_MODE: "development" | "production" (default: "development")
  DATABASE_URL: Supabase connection URL (optional for demo mode)
  SUPABASE_KEY: Supabase API key (optional)
  GOOGLE_CREDENTIALS_B64: Base64-encoded Google OAuth token (optional)
  LOG_LEVEL: "DEBUG" | "INFO" | "WARNING" | "ERROR" (default: "INFO")
  PORT: Server port (default: 8000)
  USE_DB: "true" | "false" (default: "false")
  USE_REAL_TOOLS: "true" | "false" (default: "false")
"""

import os
from pathlib import Path


class Config:
    """Production configuration manager."""

    # Deployment mode
    DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "development")
    IS_PRODUCTION = DEPLOYMENT_MODE == "production"
    IS_DEVELOPMENT = DEPLOYMENT_MODE == "development"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", None)
    SUPABASE_URL = os.getenv("SUPABASE_URL", None)
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", None)
    USE_DB = os.getenv("USE_DB", "false").lower() == "true"

    # Google OAuth
    GOOGLE_CREDENTIALS_B64 = os.getenv("GOOGLE_CREDENTIALS_B64", None)
    GOOGLE_CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials"
    GOOGLE_TOKEN_PATH = GOOGLE_CREDENTIALS_PATH / "token.json"
    GOOGLE_SECRET_PATH = GOOGLE_CREDENTIALS_PATH / "client_secret.json"

    # Execution
    USE_REAL_TOOLS = os.getenv("USE_REAL_TOOLS", "false").lower() == "true"
    EXECUTION_MODE = "production" if USE_REAL_TOOLS else "simulation"

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Timeouts
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    DECISION_TIMEOUT = int(os.getenv("DECISION_TIMEOUT", 10))

    @classmethod
    def validate(cls) -> tuple[bool, list[str]]:
        """
        Validate configuration for current deployment mode.

        Returns:
            (is_valid, list_of_warnings_or_errors)
        """
        issues = []

        if cls.IS_PRODUCTION:
            # Production requires database
            if not cls.DATABASE_URL and not (cls.SUPABASE_URL and cls.SUPABASE_KEY):
                issues.append(
                    "❌ Production mode requires DATABASE_URL or SUPABASE_URL + SUPABASE_KEY"
                )

            # Production recommends Google credentials
            if not cls.GOOGLE_CREDENTIALS_B64 and not cls.GOOGLE_SECRET_PATH.exists():
                issues.append(
                    "⚠ Production: No Google credentials found (Gmail/Calendar will fail)"
                )

        if cls.IS_DEVELOPMENT:
            if cls.USE_DB and not (cls.SUPABASE_URL and cls.SUPABASE_KEY):
                issues.append(
                    "⚠ Development: USE_DB=true but no Supabase credentials (using mock data)"
                )

        # Warnings
        if cls.USE_REAL_TOOLS and not cls.GOOGLE_CREDENTIALS_B64:
            if not cls.GOOGLE_SECRET_PATH.exists():
                issues.append(
                    "⚠ Real tools enabled but no Google credentials (will fail at runtime)"
                )

        return len([i for i in issues if i.startswith("❌")]) == 0, issues

    @classmethod
    def as_dict(cls) -> dict:
        """Return config as dictionary (safe, no secrets)."""
        return {
            "deployment_mode": cls.DEPLOYMENT_MODE,
            "is_production": cls.IS_PRODUCTION,
            "use_db": cls.USE_DB,
            "use_real_tools": cls.USE_REAL_TOOLS,
            "execution_mode": cls.EXECUTION_MODE,
            "port": cls.PORT,
            "log_level": cls.LOG_LEVEL,
            "has_database": bool(cls.DATABASE_URL or cls.SUPABASE_URL),
            "has_google_creds": bool(
                cls.GOOGLE_CREDENTIALS_B64 or cls.GOOGLE_SECRET_PATH.exists()
            ),
        }


def validate_config_on_startup():
    """Validate config and log issues at startup."""
    is_valid, issues = Config.validate()

    if issues:
        print("\n" + "=" * 60)
        print("CONFIGURATION STATUS")
        print("=" * 60)
        for issue in issues:
            print(issue)
        print("=" * 60 + "\n")

    if not is_valid and Config.IS_PRODUCTION:
        raise RuntimeError(
            "Production configuration invalid. Set required environment variables."
        )

    print(f"✅ Mode: {Config.DEPLOYMENT_MODE.upper()}")
    print(f"✅ Database: {'Enabled' if Config.USE_DB else 'Disabled (Mock)'}")
    print(
        f"✅ Real Tools: {'Enabled' if Config.USE_REAL_TOOLS else 'Disabled (Simulation)'}"
    )
