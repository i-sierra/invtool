from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Lifecycle(str, enum.Enum):
    ACTIVE = "active"  # Actively used
    OBSOLETE = "obsolete"  # No longer used
    EOL = "end-of-life"  # No longer supported
    NRND = "not-for-new-design"  # Not recommended for new designs
    NA = "n/a"  # Not applicable


class MovementReason(str, enum.Enum):
    RECEIPT = "receipt"  # Receipt of goods
    ISSUE = "issue"  # Issued goods
    TRANSFER_IN = "transfer-in"  # Transferred into inventory
    TRANSFER_OUT = "transfer-out"  # Transferred out of inventory
    ADJUST = "adjust"  # Inventory adjustment


class Preference(str, enum.Enum):
    PREFERRED = "preferred"  # Preferred option
    ALTERNATE = "alternate"  # Alternate option
    NOT_RECOMMENDED = "not-recommended"  # Not recommended option


# ------------------------------ #
#    PartType (self-relation)    #
# ------------------------------ #
class PartType(Base):
    __tablename__ = "part_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("part_types.id"), nullable=True
    )

    # Parent-Child relationship
    parent: Mapped[PartType] = relationship(
        "PartType", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[PartType]] = relationship(
        "PartType", back_populates="parent", cascade="all, delete-orphan"
    )

    # PartType <-> Part (one-to-many)
    parts: Mapped[list[Part]] = relationship("Part", back_populates="part_type")

    __table_args__ = (
        UniqueConstraint("parent_id", "code", name="uq_parttype_parent_code"),
    )


# ---------- #
#    Part    #
# ---------- #
class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ipn: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manufacturer_pn: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lifecycle: Mapped[Lifecycle] = mapped_column(
        Enum(Lifecycle), default=Lifecycle.ACTIVE, nullable=False
    )
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uom: Mapped[str] = mapped_column(String(16), default="pcs", nullable=False)
    part_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("part_types.id"), nullable=True
    )
    safety_stock: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=0
    )

    # Part <-> PartType (many-to-one)
    part_type: Mapped[PartType] = relationship("PartType", back_populates="parts")

    # Part <-> PartDistributor (one-to-many)
    part_distributors: Mapped[list[PartDistributor]] = relationship(
        "PartDistributor", back_populates="part", cascade="all, delete-orphan"
    )
    # Part <-> StockMovement (one-to-many)
    stock_movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement", back_populates="part", cascade="all, delete-orphan"
    )
    # Part <-> Document (one-to-many)
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="part", cascade="all, delete-orphan"
    )


# --------------------- #
#    Location (self)    #
# --------------------- #
class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )

    # Parent-Child relationship
    parent: Mapped[Location] = relationship(
        "Location", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[Location]] = relationship(
        "Location", back_populates="parent", cascade="all, delete-orphan"
    )

    # Location <-> StockMovement (one-to-many)
    stock_movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement", back_populates="location", cascade="all, delete-orphan"
    )


# ------------------- #
#    StockMovement    #
# ------------------- #
class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.now, nullable=False
    )
    user: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )

    qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reason: Mapped[MovementReason] = mapped_column(Enum(MovementReason), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # StockMovement <-> Part (many-to-one)
    part: Mapped[Part] = relationship("Part", back_populates="stock_movements")
    # StockMovement <-> Location (many-to-one)
    location: Mapped[Location] = relationship(
        "Location", back_populates="stock_movements"
    )


# --------------- #
#   Distributor   #
# --------------- #
class Distributor(Base):
    __tablename__ = "distributors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Distributor <-> PartDistributor (one-to-many)
    part_distributors: Mapped[list[PartDistributor]] = relationship(
        "PartDistributor", back_populates="distributor"
    )
    # Distributor <-> PurchaseOrder (one-to-many)
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        "PurchaseOrder", back_populates="distributor"
    )


# ------------------- #
#   PartDistributor   #
# ------------------- #
class PartDistributor(Base):
    __tablename__ = "part_distributors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False
    )
    distributor_id: Mapped[int] = mapped_column(
        ForeignKey("distributors.id", ondelete="RESTRICT"), nullable=False
    )
    distributor_pn: Mapped[str] = mapped_column(String(128), nullable=False)
    preference: Mapped[Preference] = mapped_column(
        Enum(Preference), nullable=False, default=Preference.ALTERNATE
    )
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "part_id", "distributor_id", "distributor_pn", name="uq_partdist_unique"
        ),
    )

    # PartDistributor <-> Part (many-to-one)
    part: Mapped[Part] = relationship("Part", back_populates="part_distributors")
    # PartDistributor <-> Distributor (many-to-one)
    distributor: Mapped[Distributor] = relationship(
        "Distributor", back_populates="part_distributors"
    )
    # PartDistributor <-> PriceBreak (one-to-many)
    price_breaks: Mapped[list[PriceBreak]] = relationship(
        "PriceBreak", back_populates="part_distributor", cascade="all, delete-orphan"
    )


# -------------- #
#   PriceBreak   #
# -------------- #
class PriceBreak(Base):
    __tablename__ = "price_breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_distributor_id: Mapped[int] = mapped_column(
        ForeignKey("part_distributors.id", ondelete="CASCADE"), nullable=False
    )
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    __table_args__ = (
        UniqueConstraint("part_distributor_id", "min_qty", name="uq_pricebreak_unique"),
    )

    # PartDistributor <-> PriceBreak (one-to-many)
    part_distributor: Mapped[PartDistributor] = relationship(
        "PartDistributor", back_populates="price_breaks"
    )


# ------------------------ #
#   Purchase Orders (PO)   #
# ------------------------ #


class POStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    distributor_id: Mapped[int] = mapped_column(
        ForeignKey("distributors.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus), nullable=False, default=POStatus.DRAFT
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.now, nullable=False
    )
    eta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # PurchaseOrder <-> Distributor (many-to-one)
    distributor: Mapped[Distributor] = relationship(
        "Distributor", back_populates="purchase_orders"
    )
    # PurchaseOrder <-> POLine (one-to-many)
    lines: Mapped[list[POLine]] = relationship(
        "POLine", back_populates="po", cascade="all, delete-orphan"
    )


class POLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False
    )
    distributor_pn: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    eta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    default_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    po: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="lines")
    part: Mapped[Part] = relationship("Part")
    default_location: Mapped[Location | None] = relationship("Location")


# --------------------------- #
#   Documents (attachments)   #
# --------------------------- #


class DocumentKind(str, enum.Enum):
    DELIVERY = "delivery"
    DATASHEET = "datasheet"
    MANUAL = "manual"
    DRAWING = "drawing"
    SPEC = "spec"
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.now, nullable=False
    )

    # Document <-> StockMovement (many-to-one)
    stock_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_movements.id", ondelete="CASCADE"), nullable=True
    )
    # Document <-> Part (many-to-one)
    part_id: Mapped[int | None] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=True
    )
    # Document <-> StockMovement (many-to-one)
    stock_movement: Mapped[StockMovement] = relationship(
        "StockMovement", backref="documents"
    )
    # Document <-> Part (many-to-one)
    part: Mapped[Part] = relationship("Part", back_populates="documents")
