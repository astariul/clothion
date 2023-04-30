from dataclasses import dataclass

from omegaconf import OmegaConf as omg
from omegaconf.errors import ConfigKeyError


USR_PATTERN = "<USERNAME>"
PWD_PATTERN = "<PASSWORD>"
DATABASE_PROFILES = {
    "local": "sqlite://",
    "test": f"postgresql://{USR_PATTERN}:{PWD_PATTERN}@TODO/db",
    "prod": f"postgresql://{USR_PATTERN}:{PWD_PATTERN}@TODO/db",
}


@dataclass
class DefaultConfig:
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    db: str = "local"
    db_url: str = f"{DATABASE_PROFILES[db]}"
    db_username: str = ""
    db_password: str = ""


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
