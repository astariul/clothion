from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from clothion.database import Base


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)

    tables = relationship("Table", back_populates="integration")


class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(String, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"))

    integration = relationship("Integration", back_populates="tables")
