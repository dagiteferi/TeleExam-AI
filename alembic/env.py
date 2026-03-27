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

# Let's use the URL directly from our settings. 
# We assume it is already properly encoded in the .env if it contains special characters.
db_url = settings.sqlalchemy_database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", db_url)

from app.db.postgres import Base
import app.models  # Ensure models are loaded

target_metadata = Base.metadata


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