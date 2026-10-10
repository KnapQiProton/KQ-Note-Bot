import os
from dataclasses import dataclass

# Baca file .env jika tersedia
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))

@dataclass
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Jakarta")
    PORT: int = int(os.getenv("PORT", "8080"))
    WEB_APP_URL: str = os.getenv("WEB_APP_URL", "")

    @property
    def dashboard_url(self) -> str:
        if self.WEB_APP_URL:
            return self.WEB_APP_URL.rstrip("/")
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
        if railway_domain:
            return f"https://{railway_domain}"
        return f"http://localhost:{self.PORT}"

    @property
    def async_database_url(self) -> str:
        """
        Railway standard PostgreSQL URL starts with 'postgresql://' or 'postgres://'.
        SQLAlchemy async engine dengan asyncpg memerlukan 'postgresql+asyncpg://'.
        """
        url = self.DATABASE_URL.strip()
        if not url:
            return ""
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

settings = Settings()
