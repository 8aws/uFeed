from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="dev")
    log_level: str = Field(default="info")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ufeed:change-me@db:5432/ufeed",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://ufeed:change-me@db:5432/ufeed",
    )

    # Cache / queues
    redis_url: str = Field(default="redis://cache:6379/0")

    # Auth (used from WS1 onwards)
    jwt_secret: str = Field(default="change-me")
    jwt_access_ttl_min: int = Field(default=15)
    jwt_refresh_ttl_days: int = Field(default=30)

    # i18n
    default_locale: str = Field(default="en")
    supported_locales: tuple[str, ...] = ("en", "es")

    # CORS
    cors_origins: str = Field(default="http://localhost:5173")

    # Ingestion worker
    ingest_tick_s: int = Field(default=60)  # how often the scheduler wakes up
    ingest_batch: int = Field(default=20)  # max sources processed per tick
    # Activity-driven ingest: the worker only polls feeds followed by someone
    # active (web or API key) within this window; returning users trigger a
    # sync of their own feeds on app open (POST /api/sync).
    ingest_active_window_h: int = Field(default=6)
    sync_cooldown_s: int = Field(default=300)  # per user, separate from plan limits
    sync_budget_s: float = Field(default=12.0)  # max time a sync request waits
    ingest_default_interval_s: int = Field(default=900)  # base poll interval
    ingest_max_interval_s: int = Field(default=21_600)  # backoff cap (6h)
    http_timeout_s: float = Field(default=20.0)
    user_agent: str = Field(default="uFeed/0.1 (+https://github.com/8aws/uFeed)")
    # Fetch each new article page to recover og:image when the feed omits it.
    og_image_max_per_source: int = Field(default=6)

    # Rate limiting (fixed window per minute; 0 disables)
    rate_limit_public_per_min: int = Field(default=120)
    rate_limit_auth_per_min: int = Field(default=20)

    # AI service (embeddings / summaries). Fails open when unreachable.
    ai_url: str = Field(default="http://ai:8001")
    ai_enabled: bool = Field(default=True)
    embedding_dim: int = Field(default=384)
    embed_max_per_tick: int = Field(default=50)
    summarize_max_per_tick: int = Field(default=20)
    ai_summary_sentences: int = Field(default=4)
    # On-device LLM (abstractive summaries in the reader's language).
    ai_llm_timeout_s: float = Field(default=120.0)
    ai_llm_per_hour: int = Field(default=30)  # generations per user per hour
    # Server voice ("listen"): languages with a voice in the AI service, MP3
    # cache (LRU, shared by all readers), generations per user per hour.
    tts_langs: str = Field(default="es,en")
    tts_cache_dir: str = Field(default="/data/tts")
    tts_cache_max_mb: int = Field(default=1024)
    tts_per_hour: int = Field(default=30)
    tts_timeout_s: float = Field(default=240.0)
    tts_voice_tag: str = Field(default="v1")  # bump to regenerate cached audio
    # Machine translation ("read in my language"): pairs with an exported model.
    mt_pairs: str = Field(default="en-es,es-en")
    mt_timeout_s: float = Field(default=120.0)
    mt_per_hour: int = Field(default=60)
    # Full article text fetched from the publisher's page (per user per hour).
    full_per_hour: int = Field(default=120)
    # Allow fetching feeds on private/LAN addresses (SSRF guard off). Only for
    # trusted single-user installs.
    allow_private_feeds: bool = Field(default=False)
    # Where backups/status.json is readable (mounted read-only in production).
    backups_dir: str = Field(default="/backups")
    # Near-duplicate grouping: lower cosine distance = stricter. Tune up (~0.2)
    # with real semantic embeddings on the NAS; ~0.1 suits the hashing backend.
    dedup_threshold: float = Field(default=0.12)
    dedup_max_per_tick: int = Field(default=100)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
