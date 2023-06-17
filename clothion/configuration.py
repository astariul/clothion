"""Configuration declaration & parsing."""
from dataclasses import dataclass

from omegaconf import OmegaConf as omg
from omegaconf.errors import ConfigKeyError


USR_PATTERN = "<USERNAME>"
PWD_PATTERN = "<PASSWORD>"
DATABASE_PROFILES = {
    "memory": "sqlite://",
    "local": "sqlite:///db.sql",
    "test": f"postgresql://{USR_PATTERN}:{PWD_PATTERN}@TODO/db",
    "prod": f"postgresql://{USR_PATTERN}:{PWD_PATTERN}@TODO/db",
}


omg.register_new_resolver("db_url", lambda profile_name: DATABASE_PROFILES[profile_name])


@dataclass
class DefaultConfig:
    """Default configuration, with sensible defaults whenever possible."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    db: str = "${oc.env:CLOTHION_DB,local}"
    db_url: str = "${db_url:${db}}"
    db_username: str = "${oc.env:CLOTHION_DB_USR,''}"
    db_password: str = "${oc.env:CLOTHION_DB_PWD,''}"


config = omg.structured(DefaultConfig)

# Get any config from CLI, and try to merge it
# If there is an error, ignore CLI (happens when calling another command, like alembic)
cli_conf = omg.from_cli()
try:
    config = omg.merge(config, cli_conf)
except ConfigKeyError:
    pass

# Replace username and password in the database URL from the given arguments
config.db_url = DATABASE_PROFILES[config.db]
config.db_url = config.db_url.replace(USR_PATTERN, config.db_username).replace(PWD_PATTERN, config.db_password)
