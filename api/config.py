"""
api/config.py — API settings.

SUPABASE_URL/SUPABASE_KEY are read directly by data/supabase_client.py's
_secret() fallback (os.environ), not duplicated here. This module only
covers settings specific to the API process itself (CORS).

Loads a .env file (repo root or api/.env, python-dotenv searches upward)
before Settings() is constructed, so SUPABASE_URL/SUPABASE_KEY are already
in os.environ by the time anything calls data.supabase_client.get_client().
"""

from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Comma-separated in .env, e.g. CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
