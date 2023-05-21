from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
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
    elements = relationship("Element", back_populates="table")


class Element(Base):
    __tablename__ = "elements"

    id = Column(Integer, primary_key=True, index=True)
    last_edited = Column(DateTime)
    notion_id = Column(String, unique=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"))

    table = relationship("Table", back_populates="elements")
    attributes = relationship("Attribute", back_populates="element", passive_deletes=True)


class Attribute(Base):
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
    parts = relationship("StringPart", back_populates="attribute", passive_deletes=True)


class StringPart(Base):
    __tablename__ = "stringparts"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)
    attribute_id = Column(Integer, ForeignKey("attributes.id", ondelete="CASCADE"))

    attribute = relationship("Attribute", back_populates="parts")
