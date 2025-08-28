import sqlalchemy as sa
from alembic import op

revision = "0004_distributors"
down_revision = "0003_parttype_unique_per_parent"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "distributors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
    )

    op.create_table(
        "part_distributors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "part_id",
            sa.Integer,
            sa.ForeignKey("parts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "distributor_id",
            sa.Integer,
            sa.ForeignKey("distributors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("distributor_pn", sa.String(128), nullable=False),
        sa.Column(
            "preference",
            sa.Enum(
                "preferred", "alternate", "not-recommended", name="preference_enum"
            ),
            nullable=False,
            server_default="alternate",
        ),
        sa.Column("note", sa.String(256), nullable=True),
        sa.UniqueConstraint(
            "part_id", "distributor_id", "distributor_pn", name="uq_partdist_unique"
        ),
    )

    op.create_table(
        "price_breaks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "part_distributor_id",
            sa.Integer,
            sa.ForeignKey("part_distributors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("min_qty", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.UniqueConstraint(
            "part_distributor_id", "min_qty", name="uq_pricebreak_unique"
        ),
    )


def downgrade():
    op.drop_table("price_breaks")
    op.drop_table("part_distributors")
    op.drop_table("distributors")

    # Drop enum type only on dialects that support it (e.g., PostgreSQL).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TYPE IF EXISTS "preference_enum" CASCADE'))
    # For sqlite / mysql, nothing to drop
