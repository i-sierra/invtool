import sqlalchemy as sa
from alembic import op

revision = "0005_purchase_orders"
down_revision = "0004_distributors"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "distributor_id",
            sa.Integer,
            sa.ForeignKey("distributors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "open", "closed", "cancelled", name="po_status"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("eta", sa.DateTime(timezone=False), nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
    )
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "po_id",
            sa.Integer,
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.Integer,
            sa.ForeignKey("parts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("distributor_pn", sa.String(128), nullable=True),
        sa.Column("ordered_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "received_qty", sa.Numeric(18, 6), nullable=False, server_default="0"
        ),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("eta", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "default_location_id",
            sa.Integer,
            sa.ForeignKey("locations.id"),
            nullable=True,
        ),
        sa.Column("note", sa.String(256), nullable=True),
    )


def downgrade():
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")

    # Drop enum type only on dialects that support it (e.g., PostgreSQL).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TYPE IF EXISTS "po_status" CASCADE'))
    # For sqlite / mysql, nothing to drop
