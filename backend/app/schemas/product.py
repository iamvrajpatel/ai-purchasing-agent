from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    id: int
    sku: str
    name: str
    description: str | None
    category: str
    unit_volume: Decimal
    safety_stock: int
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseRead(BaseModel):
    id: int
    name: str
    location: str
    total_storage_capacity: Decimal
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierRead(BaseModel):
    id: int
    name: str
    contact_email: str
    status: str
    reliability_score: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

