"""Configuration management for CineSeeker."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env file
load_dotenv()

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config.yaml."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Database
    database_url: Optional[str] = None

    # Image Search API Keys
    yandex_api_key: Optional[str] = None
    serpapi_key: Optional[str] = None

    # Movie Metadata API Keys
    tmdb_api_key: Optional[str] = None
    omdb_api_key: Optional[str] = None

    # Search Engine Settings
    google_dork_timeout: int = 10
    max_search_results: int = 50
    concurrent_crawlers: int = 5

    # Proxy (optional)
    proxy_url: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @classmethod
    def load_yaml_config(cls) -> dict:
        """Load crawler configs from config.yaml."""
        yaml_path = ROOT_DIR / "config" / "config.yaml"
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @classmethod
    def get_crawler_sites(cls) -> list[dict]:
        """Get the list of configured crawler sites from YAML."""
        config = cls.load_yaml_config()
        return config.get("crawlers", {}).get("sites", [])

    @classmethod
    def get_google_dork_queries(cls) -> list[dict]:
        """Get Google Dork query templates from YAML."""
        config = cls.load_yaml_config()
        return config.get("search", {}).get("dork_queries", [])


settings = Settings()
