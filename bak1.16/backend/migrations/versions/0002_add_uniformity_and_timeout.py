"""add uniformity index and timeout tracking

Revision ID: 002
Revises: 001
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_data_at to runs table for timeout tracking
    op.add_column('runs', sa.Column('last_data_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add uniformity_index to telemetry_samples table
    op.add_column('telemetry_samples', sa.Column('uniformity_index', sa.Float(), nullable=True))
    
    # Remove alt_m and heading_deg from gps_points table
    op.drop_column('gps_points', 'alt_m')
    op.drop_column('gps_points', 'heading_deg')


def downgrade():
    # Restore alt_m and heading_deg to gps_points table
    op.add_column('gps_points', sa.Column('heading_deg', sa.Float(), nullable=True))
    op.add_column('gps_points', sa.Column('alt_m', sa.Float(), nullable=True))
    
    # Remove uniformity_index from telemetry_samples table
    op.drop_column('telemetry_samples', 'uniformity_index')
    
    # Remove last_data_at from runs table
    op.drop_column('runs', 'last_data_at')

