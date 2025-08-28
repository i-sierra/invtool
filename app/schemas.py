from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models import Lifecycle

# -------- PartType --------


class PartTypeCreate(BaseModel):
    code: str
    label: str
    parent_id: Optional[int] = None


class PartTypeRead(BaseModel):
    id: int
    code: str
    label: str
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


# -------- Location --------


class LocationCreate(BaseModel):
    code: str = Field(..., min_length=1)
    name: str
    parent_id: Optional[int] = None


class LocationRead(BaseModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


# -------- Stock movements (requests) --------


class StockBase(BaseModel):
    ipn: str
    location_code: str
    qty: Decimal = Field(..., gt=0)


class ReceiptRequest(StockBase):
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    note: Optional[str] = None


class IssueRequest(StockBase):
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    note: Optional[str] = None


class AdjustRequest(StockBase):
    direction: int = Field(
        ..., ge=-1, le=1, description="Use +1 for addition, -1 for subtraction"
    )
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    note: Optional[str] = None


class TransferRequest(BaseModel):
    ipn: str
    from_location: str
    to_location: str
    qty: Decimal = Field(..., gt=0)
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    note: Optional[str] = None


# -------- Responses / Queries --------


class StockByLocation(BaseModel):
    location_code: str
    qty: Decimal


class StockSnapshot(BaseModel):
    ipn: str
    total_on_hand: Decimal
    by_location: List[StockByLocation]


# -------- Part --------


class PartCreate(BaseModel):
    ipn: Optional[str] = Field(None, min_length=9, max_length=9)
    description: str = Field(..., min_length=1, max_length=512)
    manufacturer: Optional[str] = Field(None, max_length=128)
    manufacturer_pn: Optional[str] = Field(None, max_length=128)
    lifecycle: Lifecycle = Lifecycle.ACTIVE
    is_compound: bool = False
    uom: str = "pcs"
    part_type_id: Optional[int] = None


class PartUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=512)
    manufacturer: Optional[str] = Field(None, max_length=128)
    manufacturer_pn: Optional[str] = Field(None, max_length=128)
    is_compound: Optional[bool] = None
    uom: Optional[str] = None
    part_type_id: Optional[int] = None


class PartRead(BaseModel):
    id: int
    ipn: str
    description: str
    manufacturer: Optional[str]
    manufacturer_pn: Optional[str]
    is_compound: bool
    uom: str
    part_type_id: Optional[int]

    class Config:
        from_attributes = True


# -------- Distributor catalog --------


class DistributorCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=64)


class DistributorUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)


class DistributorRead(BaseModel):
    id: int
    code: str
    name: str

    class Config:
        from_attributes = True


# -------- Part-distributor & price breaks --------


class PriceBreakCreate(BaseModel):
    part_distributor_id: int
    min_qty: int
    unit_price: Decimal
    currency: str = Field(default="EUR", max_length=3)


class PriceBreakRead(BaseModel):
    id: int
    part_distributor_id: int
    min_qty: int
    unit_price: Decimal
    currency: str

    class Config:
        from_attributes = True


class PartDistributorCreate(BaseModel):
    distributor_id: int
    distributor_pn: str = Field(..., max_length=128)
    preference: str = Field("alternate")
    note: Optional[str] = Field(None, max_length=256)


class PartDistributorUpdate(BaseModel):
    distributor_pn: Optional[str] = Field(None, max_length=128)
    preference: Optional[str] = None
    note: Optional[str] = Field(None, max_length=256)


class PartDistributorRead(BaseModel):
    id: int
    distributor: DistributorRead
    distributor_pn: str
    preference: str
    note: Optional[str]
    price_breaks: list[PriceBreakRead]

    class Config:
        from_attributes = True


# -------- Purchase orders --------


class POLineCreate(BaseModel):
    part_id: int
    ordered_qty: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = None
    distributor_pn: Optional[str] = None
    eta: Optional[datetime] = None
    default_location_id: Optional[int] = None
    note: Optional[str] = None


class POLineRead(BaseModel):
    id: int
    part_id: int
    ordered_qty: Decimal
    received_qty: Decimal
    unit_price: Optional[Decimal]
    distributor_pn: Optional[str]
    eta: Optional[datetime]
    default_location_id: Optional[int]
    note: Optional[str]

    class Config:
        from_attributes = True


class POCreate(BaseModel):
    code: str
    distributor_id: int
    currency: str = "EUR"
    eta: Optional[datetime] = None
    note: Optional[str] = None


class PORead(BaseModel):
    id: int
    code: str
    distributor_id: int
    status: str
    currency: str
    created_at: datetime
    eta: Optional[datetime]
    note: Optional[str]
    lines: List[POLineRead]

    class Config:
        from_attributes = True


class POReceiveLineRequest(BaseModel):
    line_id: int
    qty: Decimal = Field(..., gt=0)
    location_code: Optional[str] = None
    note: Optional[str] = None
