from alembic import op
import sqlalchemy as sa

revision = "0006_po_extras_and_docs"  # tu id real
down_revision = "0005_purchase_orders"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Add parts.safety_stock if missing
    existing_cols = [c["name"] for c in insp.get_columns("parts")]
    if "safety_stock" not in existing_cols:
        op.add_column(
            "parts",
            sa.Column(
                "safety_stock", sa.Numeric(18, 6), nullable=False, server_default="0"
            ),
        )
        # Remove the server_default only in engines that support it (not SQLite)
        if bind.dialect.name != "sqlite":
            op.alter_column("parts", "safety_stock", server_default=None)

    # 2) Create documents table if not present
    if not insp.has_table("documents"):
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "kind", sa.Enum("delivery-note", name="document_kind"), nullable=False
            ),
            sa.Column("file_path", sa.String(512), nullable=False),
            sa.Column("file_name", sa.String(256), nullable=False),
            sa.Column("mime_type", sa.String(64), nullable=True),
            sa.Column("size", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
            sa.Column(
                "stock_movement_id",
                sa.Integer,
                sa.ForeignKey("stock_movements.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Drop documents table (and enum only in PostgreSQL)
    if insp.has_table("documents"):
        op.drop_table("documents")
        if bind.dialect.name == "postgresql":
            op.execute(sa.text('DROP TYPE IF EXISTS "document_kind" CASCADE'))

    # Drop parts.safety_stock if exists
    existing_cols = [c["name"] for c in insp.get_columns("parts")]
    if "safety_stock" in existing_cols:
        op.drop_column("parts", "safety_stock")
