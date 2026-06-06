"""perfil banimento logs

Revision ID: c3d4e5f6a7b8
Revises: b2c5d6e7f8a9
Create Date: 2026-06-05 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('nome_exibicao', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('biografia', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('criado_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('motivo_banimento', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('data_banimento', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('data_desbanimento', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('pref_email', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('pref_novos_lances', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('pref_leiloes_encerrados', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('mostrar_cidade', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('mostrar_telefone', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('mostrar_email', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('banido', sa.Boolean(), nullable=True))

    op.execute("UPDATE user SET foto = 'sem-imagem.png' WHERE foto IS NULL")
    op.execute("UPDATE user SET criado_em = CURRENT_TIMESTAMP WHERE criado_em IS NULL")
    op.execute("UPDATE user SET pref_email = 1 WHERE pref_email IS NULL")
    op.execute("UPDATE user SET pref_novos_lances = 1 WHERE pref_novos_lances IS NULL")
    op.execute("UPDATE user SET pref_leiloes_encerrados = 1 WHERE pref_leiloes_encerrados IS NULL")
    op.execute("UPDATE user SET mostrar_cidade = 1 WHERE mostrar_cidade IS NULL")
    op.execute("UPDATE user SET mostrar_telefone = 0 WHERE mostrar_telefone IS NULL")
    op.execute("UPDATE user SET mostrar_email = 0 WHERE mostrar_email IS NULL")
    op.execute("UPDATE user SET banido = 0 WHERE banido IS NULL")

    op.create_table(
        'log_acao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('acao', sa.String(length=100), nullable=False),
        sa.Column('detalhes', sa.Text(), nullable=True),
        sa.Column('data', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('log_acao')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('mostrar_email')
        batch_op.drop_column('mostrar_telefone')
        batch_op.drop_column('mostrar_cidade')
        batch_op.drop_column('banido')
        batch_op.drop_column('pref_leiloes_encerrados')
        batch_op.drop_column('pref_novos_lances')
        batch_op.drop_column('pref_email')
        batch_op.drop_column('data_desbanimento')
        batch_op.drop_column('data_banimento')
        batch_op.drop_column('motivo_banimento')
        batch_op.drop_column('criado_em')
        batch_op.drop_column('biografia')
        batch_op.drop_column('nome_exibicao')
        batch_op.drop_column('foto')
