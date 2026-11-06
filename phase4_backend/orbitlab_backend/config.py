"""Pydantic-settings config for OrbitLab backend.

All secrets come from environment variables; missing required vars raise
a clear message naming the variable, never printing values.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    HAS_PYDANTIC_SETTINGS = False
    # Fallback minimal implementation if pydantic-settings not installed
    BaseSettings = object  # type: ignore
    SettingsConfigDict = dict  # type: ignore

if HAS_PYDANTIC_SETTINGS:

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        # Interpreter (hosted model that returns experiment JSON)
        ORBITLAB_MODEL_URL: Optional[str] = Field(default=None)
        ORBITLAB_MODEL_KEY: Optional[str] = Field(default=None)
        ORBITLAB_MODEL_TIMEOUT_S: float = Field(default=180.0)
        ORBITLAB_MODEL_NAME: Optional[str] = Field(default=None)
        ORBITLAB_MODEL_MAX_TOKENS: int = Field(default=1500)
        # Measured GMAT cost, seconds of wall time per simulated day (worst
        # case seen: Mars 687 d finished in 317.8 s => 317.8/687 = 0.4626,
        # rounded up to 0.5 to stay conservative). Used only for timeout
        # estimates; lowering accuracy is never a substitute (see Step 4).
        ORBITLAB_GMAT_SECS_PER_SIM_DAY: float = Field(default=0.5)
        ORBITLAB_GMAT_MAX_TIMEOUT_S: float = Field(default=900.0)
        ORBITLAB_PROGRESS_INTERVAL_S: float = Field(default=10.0)

        # Front-step extractor + explainer (OpenAI-compatible)
        EXTRACTOR_BASE_URL: Optional[str] = Field(default=None)
        EXTRACTOR_API_KEY: Optional[str] = Field(default=None)
        EXTRACTOR_MODEL: Optional[str] = Field(default=None)
        EXTRACTOR_JSON_MODE: str = Field(default="prompt")

        # GMAT
        GMAT_PATH: Optional[str] = Field(default=None)
        GMAT_TIMEOUT_S: float = Field(default=30.0)

        # API / CORS
        ORBITLAB_CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000")
        # If true, use mock interpreter instead of real HTTP
        ORBITLAB_USE_MOCK_INTERPRETER: bool = Field(default=False)
        ORBITLAB_RUN_DIR: Optional[str] = Field(default=None)
        ORBITLAB_RUN_RETENTION_HOURS: float = Field(default=24.0)

        def require(self, name: str) -> str:
            val = getattr(self, name, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise RuntimeError(f"Missing required environment variable: {name}")
            return val  # type: ignore

        def cors_origins_list(self):
            if self.ORBITLAB_CORS_ORIGINS == "*":
                return ["*"]
            return [o.strip() for o in self.ORBITLAB_CORS_ORIGINS.split(",") if o.strip()]

else:

    class Settings:  # type: ignore
        def __init__(self, **kwargs):
            self.ORBITLAB_MODEL_URL = os.getenv("ORBITLAB_MODEL_URL")
            self.ORBITLAB_MODEL_KEY = os.getenv("ORBITLAB_MODEL_KEY")
            self.ORBITLAB_MODEL_TIMEOUT_S = float(os.getenv("ORBITLAB_MODEL_TIMEOUT_S", "180"))
            self.ORBITLAB_MODEL_NAME = os.getenv("ORBITLAB_MODEL_NAME")
            self.ORBITLAB_MODEL_MAX_TOKENS = int(os.getenv("ORBITLAB_MODEL_MAX_TOKENS", "1500"))
            self.ORBITLAB_GMAT_SECS_PER_SIM_DAY = float(os.getenv("ORBITLAB_GMAT_SECS_PER_SIM_DAY", "0.5"))
            self.ORBITLAB_GMAT_MAX_TIMEOUT_S = float(os.getenv("ORBITLAB_GMAT_MAX_TIMEOUT_S", "900"))
            self.ORBITLAB_PROGRESS_INTERVAL_S = float(os.getenv("ORBITLAB_PROGRESS_INTERVAL_S", "10"))
            self.EXTRACTOR_BASE_URL = os.getenv("EXTRACTOR_BASE_URL")
            self.EXTRACTOR_API_KEY = os.getenv("EXTRACTOR_API_KEY")
            self.EXTRACTOR_MODEL = os.getenv("EXTRACTOR_MODEL")
            self.EXTRACTOR_JSON_MODE = os.getenv("EXTRACTOR_JSON_MODE", "prompt")
            self.GMAT_PATH = os.getenv("GMAT_PATH")
            self.GMAT_TIMEOUT_S = float(os.getenv("GMAT_TIMEOUT_S", "30"))
            self.ORBITLAB_CORS_ORIGINS = os.getenv("ORBITLAB_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000")
            self.ORBITLAB_USE_MOCK_INTERPRETER = os.getenv("ORBITLAB_USE_MOCK_INTERPRETER", "false").lower() in ("1", "true", "yes")
            self.ORBITLAB_RUN_DIR = os.getenv("ORBITLAB_RUN_DIR")
            self.ORBITLAB_RUN_RETENTION_HOURS = float(os.getenv("ORBITLAB_RUN_RETENTION_HOURS", "24"))

        def require(self, name: str) -> str:
            val = getattr(self, name, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise RuntimeError(f"Missing required environment variable: {name}")
            return val

        def cors_origins_list(self):
            if self.ORBITLAB_CORS_ORIGINS == "*":
                return ["*"]
            return [o.strip() for o in self.ORBITLAB_CORS_ORIGINS.split(",") if o.strip()]

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore
    return _settings

def reset_settings():
    global _settings
    _settings = None
