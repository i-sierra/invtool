from alembic import op
import sqlalchemy as sa

revision = "0008_counters_and_movement_code"
down_revision = "0007_part_documents_and_kinds"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) counters table (create if missing)
    if not insp.has_table("counters"):
        op.create_table(
            "counters",
            sa.Column("name", sa.String(32), nullable=False),
            sa.Column("scope1", sa.String(32), nullable=True),
            sa.Column("scope2", sa.String(32), nullable=True),
            sa.Column("seq", sa.Integer, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
            sa.PrimaryKeyConstraint("name", "scope1", "scope2", name="pk_counters"),
        )
        op.create_index("ix_counters_name_scope", "counters", ["name", "scope1", "scope2"])

    # 2) stock_movements.code (add column and UNIQUE in one rebuild for SQLite)
    existing_cols = {c["name"] for c in insp.get_columns("stock_movements")}
    existing_ucs = {uc["name"] or "" for uc in insp.get_unique_constraints("stock_movements")}

    with op.batch_alter_table("stock_movements", recreate="always") as batch:
        if "code" not in existing_cols:
            batch.add_column(sa.Column("code", sa.String(32), nullable=True))
        if "uq_stock_movements_code" not in existing_ucs:
            batch.create_unique_constraint("uq_stock_movements_code", ["code"])

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Drop UNIQUE + column via rebuild
    existing_cols = {c["name"] for c in insp.get_columns("stock_movements")}
    existing_ucs = {uc["name"] or "" for uc in insp.get_unique_constraints("stock_movements")}
    with op.batch_alter_table("stock_movements", recreate="always") as batch:
        if "uq_stock_movements_code" in existing_ucs:
            batch.drop_constraint("uq_stock_movements_code", type_="unique")
        if "code" in existing_cols:
            batch.drop_column("code")

    # Drop counters (index first), only if exists
    if insp.has_table("counters"):
        # index may or may not exist depending de versión previa; inténtalo con try:
        try:
            op.drop_index("ix_counters_name_scope", table_name="counters")
        except Exception:
            pass
        op.drop_table("counters")
