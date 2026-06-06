"""data criacao leilao

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-06 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leilao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_criacao', sa.DateTime(), nullable=True))

    op.execute("UPDATE leilao SET data_criacao = CURRENT_TIMESTAMP WHERE data_criacao IS NULL")


def downgrade():
    with op.batch_alter_table('leilao', schema=None) as batch_op:
        batch_op.drop_column('data_criacao')
