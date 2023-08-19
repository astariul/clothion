"""Configuration declaration & parsing."""
import os
from dataclasses import dataclass

from omegaconf import OmegaConf as omg
from omegaconf.errors import ConfigKeyError


DB_PATH_PATTERN = "<DB_FILE>"
DATABASE_PROFILES = {
    "memory": "sqlite://",
    "local": f"sqlite:///{DB_PATH_PATTERN}",
}


omg.register_new_resolver("db_url", lambda profile_name: DATABASE_PROFILES[profile_name])


@dataclass
class DefaultConfig:
    """Default configuration, with sensible defaults whenever possible."""

    # Server
    host: str = "0.0.0.0"
    port: int = 9910

    # Database
    db: str = "${oc.env:CLOTHION_DB,local}"
    db_url: str = "${db_url:${db}}"
    db_path: str = "${oc.env:CLOTHION_DB_PATH,db.sql}"


config = omg.structured(DefaultConfig)

# Get any config from CLI, and try to merge it
# If there is an error, ignore CLI (happens when calling another command, like alembic)
cli_conf = omg.from_cli()
try:
    config = omg.merge(config, cli_conf)
except ConfigKeyError:
    pass

# Properly replace location of the SQLite DB in the database URL from the given arguments
config.db_url = DATABASE_PROFILES[config.db]
config.db_url = config.db_url.replace(DB_PATH_PATTERN, os.path.expanduser(config.db_path))
