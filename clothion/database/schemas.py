from typing import List

from pydantic import BaseModel


class TableBase(BaseModel):
    table_id: str


class TableCreate(TableBase):
    pass


class Table(TableBase):
    id: int
    integration_id: int

    class Config:
        orm_mode = True


class IntegrationBase(BaseModel):
    token: str


class IntegrationCreate(IntegrationBase):
    pass


class Integration(IntegrationBase):
    id: int
    tables: List[Table] = []

    class Config:
        orm_mode = True
