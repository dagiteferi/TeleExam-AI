import os
import sys
from logging.config import fileConfig
from urllib.parse import urlparse, quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to path so we can import our config
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from our secure settings
# We will parse this URL to handle special characters in password
db_url_raw = settings.sqlalchemy_database_url

# Parse the raw URL
parsed_url = urlparse(db_url_raw)

# URL-encode the password if it exists
encoded_password = quote_plus(parsed_url.password) if parsed_url.password else ""

# Reconstruct the URL with the encoded password
# Handle cases where there might not be a password or username
netloc_parts = []
if parsed_url.username:
    netloc_parts.append(parsed_url.username)
    if encoded_password:
        netloc_parts.append(f":{encoded_password}")
    netloc_parts.append("@")
elif encoded_password: # If no username but password exists, this is an invalid URL structure for standard DSN
    # This case should ideally not happen for a valid DSN, but handling defensively
    pass 

netloc = "".join(netloc_parts) + parsed_url.hostname
if parsed_url.port:
    netloc += f":{parsed_url.port}"

db_url = f"{parsed_url.scheme}://{netloc}{parsed_url.path}?{parsed_url.query}"
db_url = db_url.replace("%", "%%")

config.set_main_option("sqlalchemy.url", db_url)

# For now we don't have SQLAlchemy models (we're using raw tables)
# So we disable autogenerate for the first migration
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()