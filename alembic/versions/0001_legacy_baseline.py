"""Baseline for databases created before Alembic was introduced.

Revision ID: legacy_baseline
Revises:
"""

revision = "legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing workspaces are stamped at this revision by manage.py. Fresh
    # workspaces are bootstrapped from ORM metadata before the first upgrade.
    pass


def downgrade() -> None:
    # A baseline has no safe automatic inverse.
    pass
