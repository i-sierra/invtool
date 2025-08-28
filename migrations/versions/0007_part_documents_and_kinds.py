from alembic import op
import sqlalchemy as sa

revision = "0007_part_documents_and_kinds"
down_revision = "0006_po_extras_and_docs"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # Snapshot current schema bits
    existing_cols = {c["name"] for c in insp.get_columns("documents")}
    fk_names = {fk["name"] or "" for fk in insp.get_foreign_keys("documents")}

    if is_sqlite:
        # ---- SQLite path: do everything in one rebuild ----
        with op.batch_alter_table("documents", recreate="always") as batch:
            # 1) ensure column part_id exists
            if "part_id" not in existing_cols:
                batch.add_column(sa.Column("part_id", sa.Integer, nullable=True))

            # 2) ensure FK exists (must be created inside batch on SQLite)
            if "fk_documents_part" not in fk_names:
                batch.create_foreign_key(
                    "fk_documents_part",
                    referent_table="parts",
                    local_cols=["part_id"],
                    remote_cols=["id"],
                    ondelete="CASCADE",
                )

            # 3) extend enum (rebuilds CHECK in SQLite)
            batch.alter_column(
                "kind",
                existing_type=sa.Enum("delivery-note", name="document_kind"),
                type_=sa.Enum(
                    "delivery-note",
                    "datasheet",
                    "manual",
                    "drawing",
                    "spec",
                    "other",
                    name="document_kind",
                ),
                existing_nullable=False,
            )

    else:
        # ---- PostgreSQL / others: direct operations ----
        if "part_id" not in existing_cols:
            op.add_column("documents", sa.Column("part_id", sa.Integer, nullable=True))
        if "fk_documents_part" not in fk_names:
            op.create_foreign_key(
                "fk_documents_part",
                source_table="documents",
                referent_table="parts",
                local_cols=["part_id"],
                remote_cols=["id"],
                ondelete="CASCADE",
            )

        if bind.dialect.name == "postgresql":
            # Extend idempotent enum in PG
            for val in ["datasheet", "manual", "drawing", "spec", "other"]:
                op.execute(
                    sa.text(
                        f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type t
                        JOIN pg_enum e ON t.oid = e.enumtypid
                        WHERE t.typname = 'document_kind' AND e.enumlabel = '{val}'
                    ) THEN
                        ALTER TYPE document_kind ADD VALUE '{val}';
                    END IF;
                END$$;
                """
                    )
                )
        else:
            # MySQL and others: recreate to adjust CHECK/enum if necessary
            with op.batch_alter_table("documents", recreate="always") as batch:
                batch.alter_column(
                    "kind",
                    existing_type=sa.Enum("delivery-note", name="document_kind"),
                    type_=sa.Enum(
                        "delivery-note",
                        "datasheet",
                        "manual",
                        "drawing",
                        "spec",
                        "other",
                        name="document_kind",
                    ),
                    existing_nullable=False,
                )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # Drop FK + column inside the batch
        existing_cols = {c["name"] for c in insp.get_columns("documents")}
        fk_names = {fk["name"] or "" for fk in insp.get_foreign_keys("documents")}
        with op.batch_alter_table("documents", recreate="always") as batch:
            if "fk_documents_part" in fk_names:
                batch.drop_constraint("fk_documents_part", type_="foreignkey")
            if "part_id" in existing_cols:
                batch.drop_column("part_id")
    else:
        fk_names = {fk["name"] or "" for fk in insp.get_foreign_keys("documents")}
        if "fk_documents_part" in fk_names:
            op.drop_constraint("fk_documents_part", "documents", type_="foreignkey")
        cols = {c["name"] for c in insp.get_columns("documents")}
        if "part_id" in cols:
            op.drop_column("documents", "part_id")
