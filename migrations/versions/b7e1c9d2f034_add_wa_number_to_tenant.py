"""add wa_number to tenant

Revision ID: b7e1c9d2f034
Revises: 03c53c294d52
Create Date: 2026-05-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b7e1c9d2f034'
down_revision = '03c53c294d52'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wa_number', sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('wa_number')
