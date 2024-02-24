"""Declaration of the DB model."""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from clothion.database import Base


class Integration(Base):
    """Table to represent a Notion Integration."""

    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)

    tables = relationship("Table", back_populates="integration")


class Table(Base):
    """Table to represent a Notion Table (a Notion DB)."""

    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(String, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"))

    integration = relationship("Integration", back_populates="tables")
    elements = relationship("Element", back_populates="table")


class Element(Base):
    """Table to represent an element in a Notion Table (basically a row)."""

    __tablename__ = "elements"

    id = Column(Integer, primary_key=True, index=True)
    last_edited = Column(DateTime)
    notion_id = Column(String, unique=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"))

    table = relationship("Table", back_populates="elements")
    attributes = relationship("Attribute", back_populates="element", passive_deletes=True)


class Attribute(Base):
    """Table to represent a single attribute of a row of a Notion DB."""

    __tablename__ = "attributes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    value_bool = Column(Boolean)
    value_date = Column(DateTime)
    value_number = Column(Float)
    value_string = Column(String)
    is_bool = Column(Boolean, default=False)
    is_date = Column(Boolean, default=False)
    is_number = Column(Boolean, default=False)
    is_string = Column(Boolean, default=False)
    is_multistring = Column(Boolean, default=False)
    element_id = Column(Integer, ForeignKey("elements.id", ondelete="CASCADE"))

    element = relationship("Element", back_populates="attributes")
