"""
Environment variable loading and configuration.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables."""
    # Service Bus
    service_bus_connection_string: Optional[str] = None

    # SQL Database
    db_server: Optional[str] = None
    db_database: Optional[str] = None
    db_username: Optional[str] = None
    db_password: Optional[str] = None

    # Cosmos DB
    cosmos_endpoint: Optional[str] = None
    cosmos_key: Optional[str] = None
    cosmos_database: str = "agent-platform"

    # AI Backend
    ai_backend: str = "azure_openai"
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Load and cache application configuration from environment variables."""
    global _config
    if _config is not None:
        return _config

    _config = AppConfig(
        service_bus_connection_string=os.getenv("SERVICE_BUS_CONNECTION_STRING"),
        db_server=os.getenv("DB_SERVER"),
        db_database=os.getenv("DB_DATABASE"),
        db_username=os.getenv("DB_USERNAME"),
        db_password=os.getenv("DB_PASSWORD"),
        cosmos_endpoint=os.getenv("COSMOS_ENDPOINT"),
        cosmos_key=os.getenv("COSMOS_KEY"),
        cosmos_database=os.getenv("COSMOS_DATABASE", "agent-platform"),
        ai_backend=os.getenv("AI_BACKEND", "azure_openai"),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )

    # Warn about missing critical config
    if not _config.service_bus_connection_string:
        logging.warning("SERVICE_BUS_CONNECTION_STRING not configured")
    if not all([_config.db_server, _config.db_database, _config.db_username, _config.db_password]):
        logging.warning("Database configuration incomplete - SQL operations will fail")

    return _config
