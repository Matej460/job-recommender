"""Application settings, loaded from the .env file (or from defaults)."""

import os

from dotenv import load_dotenv

# Reads the .env file in the project root and puts its values into os.environ.
load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "jobs_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "jobs_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "jobs_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# Connection string used by SQLAlchemy. "psycopg2" is the PostgreSQL driver.
DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
