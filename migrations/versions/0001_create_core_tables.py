import sqlalchemy as sa
from alembic import op

revision = "0001_create_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "part_types",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column(
            "parent_id", sa.Integer, sa.ForeignKey("part_types.id"), nullable=True
        ),
        sa.UniqueConstraint("code", name="uq_parttype_code"),
    )
    op.create_table(
        "parts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ipn", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("manufacturer", sa.String(64), nullable=True),
        sa.Column("manufacturer_pn", sa.String(128), nullable=True),
        sa.Column(
            "lifecycle",
            sa.Enum(
                "Active",
                "Obsolete",
                "EOL",
                "NRND",
                "N/A",
                name="lifecycle_enum",
            ),
            nullable=False,
            server_default="Active",
        ),
        sa.Column("is_compound", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("uom", sa.String(16), nullable=False, server_default="pcs"),
        sa.Column("part_type_id", sa.Integer, sa.ForeignKey("part_types.id")),
    )


def downgrade():
    op.drop_table("parts")
    op.drop_table("part_types")

    # Drop enum type only on dialects that support it (e.g., PostgreSQL).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TYPE IF EXISTS "lifecycle_enum" CASCADE'))
    # For sqlite / mysql, nothing to drop
