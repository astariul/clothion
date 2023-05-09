from sqlalchemy import MetaData, create_engine, event
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
event.listen(engine, "connect", lambda dbapi_con, con_record: dbapi_con.execute("pragma foreign_keys=ON"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

meta = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
Base = declarative_base(metadata=meta)
