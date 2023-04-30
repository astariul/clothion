from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from clothion import config


kwargs = {}
if config.db_url.startswith("sqlite"):
    kwargs["connect_args"] = {"check_same_thread": False}
    if config.db == "memory":
        kwargs["poolclass"] = StaticPool

engine = create_engine(config.db_url, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
