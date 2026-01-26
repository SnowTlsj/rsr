"""add uniformity_index and last_data_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-16 02:21:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 runs 表的 last_data_at 字段
    op.add_column('runs', sa.Column('last_data_at', sa.DateTime(timezone=True), nullable=True))
    
    # 添加 telemetry_samples 表的 uniformity_index 字段
    op.add_column('telemetry_samples', sa.Column('uniformity_index', sa.Float(), nullable=True))

    # 添加通道告警字段
    op.add_column('telemetry_samples', sa.Column('alarm_channel1', sa.Integer(), nullable=True))
    op.add_column('telemetry_samples', sa.Column('alarm_channel2', sa.Integer(), nullable=True))
    op.add_column('telemetry_samples', sa.Column('alarm_channel3', sa.Integer(), nullable=True))
    op.add_column('telemetry_samples', sa.Column('alarm_channel4', sa.Integer(), nullable=True))
    op.add_column('telemetry_samples', sa.Column('alarm_channel5', sa.Integer(), nullable=True))
    
    # 删除 gps_points 表的 alt_m 和 heading_deg 字段
    op.drop_column('gps_points', 'alt_m')
    op.drop_column('gps_points', 'heading_deg')


def downgrade():
    # 恢复 gps_points 表的字段
    op.add_column('gps_points', sa.Column('heading_deg', sa.Float(), nullable=True))
    op.add_column('gps_points', sa.Column('alt_m', sa.Float(), nullable=True))
    
    # 删除通道告警字段
    op.drop_column('telemetry_samples', 'alarm_channel5')
    op.drop_column('telemetry_samples', 'alarm_channel4')
    op.drop_column('telemetry_samples', 'alarm_channel3')
    op.drop_column('telemetry_samples', 'alarm_channel2')
    op.drop_column('telemetry_samples', 'alarm_channel1')

    # 删除 telemetry_samples 表的 uniformity_index 字段
    op.drop_column('telemetry_samples', 'uniformity_index')
    
    # 删除 runs 表的 last_data_at 字段
    op.drop_column('runs', 'last_data_at')
