from dataclasses import dataclass

from omegaconf import OmegaConf as omg


USR_PATTERN = "<USERNAME>"
PWD_PATTERN = "<PASSWORD>"
DATABASE_PROFILES = {
    "local": "sqlite://?check_same_thread=False",
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


default_conf = omg.structured(DefaultConfig)
cli_conf = omg.from_cli()

config = omg.merge(default_conf, cli_conf)

# Replace username and password in the database URL from the given arguments
config.db_url = DATABASE_PROFILES[config.db]
config.db_url = config.db_url.replace(USR_PATTERN, config.db_username).replace(PWD_PATTERN, config.db_password)
