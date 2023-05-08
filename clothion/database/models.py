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
    table_id = Column(Integer, ForeignKey("tables.id"))

    table = relationship("Table", back_populates="elements")
    boolean_attributes = relationship("BooleanAttribute", back_populates="element")
    date_attributes = relationship("DateAttribute", back_populates="element")
    number_attributes = relationship("NumberAttribute", back_populates="element")
    string_attributes = relationship("StringAttribute", back_populates="element")
    multi_attributes = relationship("MultiAttribute", back_populates="element")


class BooleanAttribute(Base):
    __tablename__ = "booleans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    value = Column(Boolean)
    type = Column(String)
    element_id = Column(Integer, ForeignKey("elements.id"))

    element = relationship("Element", back_populates="boolean_attributes")


class DateAttribute(Base):
    __tablename__ = "dates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    value = Column(DateTime)
    type = Column(String)
    element_id = Column(Integer, ForeignKey("elements.id"))

    element = relationship("Element", back_populates="date_attributes")


class NumberAttribute(Base):
    __tablename__ = "numbers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    value = Column(Float)
    type = Column(String)
    element_id = Column(Integer, ForeignKey("elements.id"))

    element = relationship("Element", back_populates="number_attributes")


class StringAttribute(Base):
    __tablename__ = "strings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    value = Column(String)
    type = Column(String)
    element_id = Column(Integer, ForeignKey("elements.id"))

    element = relationship("Element", back_populates="string_attributes")


class MultiAttribute(Base):
    __tablename__ = "multis"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(String)
    element_id = Column(Integer, ForeignKey("elements.id"))

    element = relationship("Element", back_populates="multi_attributes")
    parts = relationship("MultiPartString", back_populates="multi")


class MultiPartString(Base):
    __tablename__ = "stringparts"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)
    multiattribute_id = Column(Integer, ForeignKey("multis.id"))

    multi = relationship("MultiAttribute", back_populates="parts")
