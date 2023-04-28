from dataclasses import dataclass

from omegaconf import OmegaConf as omg


@dataclass
class DefaultConfig:
    host: str = "0.0.0.0"
    port: int = 8000


default_conf = omg.structured(DefaultConfig)
cli_conf = omg.from_cli()

config = omg.merge(default_conf, cli_conf)
