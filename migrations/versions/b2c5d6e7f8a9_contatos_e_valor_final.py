"""contatos e valor final

Revision ID: b2c5d6e7f8a9
Revises: a1f4c2d9e8b7
Create Date: 2026-06-05 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c5d6e7f8a9'
down_revision = 'a1f4c2d9e8b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nome_completo', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('telefone', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('cidade', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('estado', sa.String(length=2), nullable=True))

    with op.batch_alter_table('leilao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valor_final', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('leilao', schema=None) as batch_op:
        batch_op.drop_column('valor_final')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('estado')
        batch_op.drop_column('cidade')
        batch_op.drop_column('email')
        batch_op.drop_column('telefone')
        batch_op.drop_column('nome_completo')
