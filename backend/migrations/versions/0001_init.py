"""Initial migration

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_name', sa.String(128), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_data_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )

    op.create_table(
        'telemetry_samples',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runs.id', ondelete='CASCADE'), index=True),
        sa.Column('ts', sa.DateTime(timezone=True), index=True),
        sa.Column('channel1_g', sa.Float, nullable=True),
        sa.Column('channel2_g', sa.Float, nullable=True),
        sa.Column('channel3_g', sa.Float, nullable=True),
        sa.Column('channel4_g', sa.Float, nullable=True),
        sa.Column('channel5_g', sa.Float, nullable=True),
        sa.Column('seed_total_g', sa.Float, nullable=True),
        sa.Column('distance_m', sa.Float, nullable=True),
        sa.Column('leak_distance_m', sa.Float, nullable=True),
        sa.Column('speed_kmh', sa.Float, nullable=True),
        sa.Column('uniformity_index', sa.Float, nullable=True),
        sa.Column('alarm_blocked', sa.Boolean, nullable=True),
        sa.Column('alarm_no_seed', sa.Boolean, nullable=True),
        sa.Column('alarm_channel1', sa.Integer, nullable=True),
        sa.Column('alarm_channel2', sa.Integer, nullable=True),
        sa.Column('alarm_channel3', sa.Integer, nullable=True),
        sa.Column('alarm_channel4', sa.Integer, nullable=True),
        sa.Column('alarm_channel5', sa.Integer, nullable=True),
    )

    op.create_table(
        'gps_points',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runs.id', ondelete='CASCADE'), index=True),
        sa.Column('ts', sa.DateTime(timezone=True), index=True),
        sa.Column('lon', sa.Float, nullable=False),
        sa.Column('lat', sa.Float, nullable=False),
    )

    op.create_index('ix_telemetry_run_ts', 'telemetry_samples', ['run_id', 'ts'])
    op.create_index('ix_gps_run_ts', 'gps_points', ['run_id', 'ts'])


def downgrade() -> None:
    op.drop_index('ix_gps_run_ts', table_name='gps_points')
    op.drop_index('ix_telemetry_run_ts', table_name='telemetry_samples')
    op.drop_table('gps_points')
    op.drop_table('telemetry_samples')
    op.drop_table('runs')


