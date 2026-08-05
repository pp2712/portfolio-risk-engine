"""rename prices.raw_close to close

Revision ID: 2d94fb0fed51
Revises: 2ef65d9a4df0
Create Date: 2026-08-05 16:31:52.357802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d94fb0fed51'
down_revision: Union[str, Sequence[str], None] = '2ef65d9a4df0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename in place -- autogenerate detected this as add+drop, which would lose data and
    violate the NOT NULL constraint on a table that already has rows. A real rename instead."""
    op.alter_column('prices', 'raw_close', new_column_name='close')


def downgrade() -> None:
    op.alter_column('prices', 'close', new_column_name='raw_close')
