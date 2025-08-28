import sqlalchemy as sa
from alembic import op

revision = "0002_inventory_core"
down_revision = "0001_create_core_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "parent_id", sa.Integer, sa.ForeignKey("locations.id"), nullable=True
        ),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column("user", sa.String(64), nullable=True),
        sa.Column(
            "part_id",
            sa.Integer,
            sa.ForeignKey("parts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer,
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "receipt",
                "issue",
                "transfer-in",
                "transfer-out",
                "adjust",
                name="movementreason",
            ),
            nullable=False,
        ),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.String(64), nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
    )


def downgrade():
    op.drop_table("stock_movements")
    op.drop_table("locations")

    # Drop enum type only on dialects that support it (e.g., PostgreSQL).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TYPE IF EXISTS "movementreason" CASCADE'))
    # For sqlite / mysql, nothing to drop
