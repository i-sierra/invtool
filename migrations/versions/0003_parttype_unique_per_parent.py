from alembic import op

revision = "0003_parttype_unique_per_parent"
down_revision = "0002_inventory_core"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("part_types", schema=None) as batch_op:
        # Elimina la antigua unicidad global por 'code'
        batch_op.drop_constraint("uq_parttype_code", type_="unique")
        # Crea la nueva unicidad por (parent_id, code)
        batch_op.create_unique_constraint(
            "uq_parttype_parent_code", ["parent_id", "code"]
        )


def downgrade():
    with op.batch_alter_table("part_types", schema=None) as batch_op:
        batch_op.drop_constraint("uq_parttype_parent_code", type_="unique")
        batch_op.create_unique_constraint("uq_parttype_code", ["code"])
