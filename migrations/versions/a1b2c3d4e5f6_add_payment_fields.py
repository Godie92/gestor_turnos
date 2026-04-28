"""add payment_status and mp_access_token

Revision ID: a1b2c3d4e5f6
Revises: 5e8b829dc535
Create Date: 2026-04-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '5e8b829dc535'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'appointments'"
    ))
    appointments_columns = {row[0] for row in result}

    with op.batch_alter_table('appointments', schema=None) as batch_op:
        if 'payment_status' not in appointments_columns:
            batch_op.add_column(sa.Column('payment_status', sa.String(length=20), nullable=True))

    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'tenants'"
    ))
    tenants_columns = {row[0] for row in result}

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        if 'mp_access_token' not in tenants_columns:
            batch_op.add_column(sa.Column('mp_access_token', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('mp_access_token')

    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.drop_column('payment_status')
