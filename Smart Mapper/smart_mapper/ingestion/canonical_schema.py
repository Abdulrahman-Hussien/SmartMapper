from __future__ import annotations

from pydantic import BaseModel


class RawCustomerRow(BaseModel):
    code: str
    name: str
    address: str
    city: str | None = None
    phone: str | None = None
