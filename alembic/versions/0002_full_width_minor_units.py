"""Store minor-unit monetary values in signed 64-bit columns.

Revision ID: full_width_minor_units
Revises: legacy_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "full_width_minor_units"
down_revision = "legacy_baseline"
branch_labels = None
depends_on = None

MONEY_COLUMNS = {
    "statement_reconciliations": (
        "opening_balance_minor", "closing_balance_minor", "calculated_balance_minor",
        "total_credits_minor", "total_debits_minor", "error_margin_minor",
    ),
    "transfers": ("amount_minor",),
    "seam_matches": ("inr_amount_minor", "usdt_amount_minor"),
}


def _alter_minor_unit_width(target_type) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name, columns in MONEY_COLUMNS.items():
        if table_name not in inspector.get_table_names():
            raise RuntimeError(f"Expected table {table_name!r} is missing; refusing partial migration")
        reflected = {column["name"]: column["type"] for column in inspector.get_columns(table_name)}
        changes = [(name, reflected[name]) for name in columns if name in reflected]
        if len(changes) != len(columns):
            raise RuntimeError(f"Expected monetary column is missing from {table_name!r}")
        if all(isinstance(current, target_type) for _, current in changes):
            continue
        with op.batch_alter_table(table_name) as batch:
            for column_name, current_type in changes:
                if isinstance(current_type, target_type):
                    continue
                batch.alter_column(
                    column_name,
                    existing_type=current_type,
                    existing_nullable=False,
                    type_=target_type(),
                )
        inspector = sa.inspect(bind)


def upgrade() -> None:
    _alter_minor_unit_width(sa.BigInteger)


def downgrade() -> None:
    _alter_minor_unit_width(sa.Integer)
