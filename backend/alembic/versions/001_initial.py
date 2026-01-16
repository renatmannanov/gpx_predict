"""Initial migration - create all tables

Revision ID: 001_initial
Revises:
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('telegram_id', sa.String(20), unique=True, index=True, nullable=True),
        sa.Column('email', sa.String(255), unique=True, index=True, nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('strava_athlete_id', sa.String(20), nullable=True),
        sa.Column('strava_connected', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Create gpx_files table
    op.create_table(
        'gpx_files',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('gpx_content', sa.LargeBinary(), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('elevation_gain_m', sa.Float(), nullable=True),
        sa.Column('elevation_loss_m', sa.Float(), nullable=True),
        sa.Column('max_elevation_m', sa.Float(), nullable=True),
        sa.Column('min_elevation_m', sa.Float(), nullable=True),
        sa.Column('start_lat', sa.Float(), nullable=True),
        sa.Column('start_lon', sa.Float(), nullable=True),
        sa.Column('end_lat', sa.Float(), nullable=True),
        sa.Column('end_lon', sa.Float(), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Create predictions table
    op.create_table(
        'predictions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('prediction_type', sa.Enum('hike', 'run', name='predictiontype'), default='hike'),
        sa.Column('gpx_file_id', sa.String(36), sa.ForeignKey('gpx_files.id'), nullable=True),
        sa.Column('experience', sa.Enum('beginner', 'casual', 'regular', 'experienced', name='experiencelevel'), nullable=True),
        sa.Column('backpack', sa.Enum('light', 'medium', 'heavy', name='backpackweight'), nullable=True),
        sa.Column('group_size', sa.Integer(), default=1),
        sa.Column('has_children', sa.Integer(), default=0),
        sa.Column('has_elderly', sa.Integer(), default=0),
        sa.Column('known_time_seconds', sa.Integer(), nullable=True),
        sa.Column('known_distance_km', sa.Float(), nullable=True),
        sa.Column('estimated_time_hours', sa.Float(), nullable=True),
        sa.Column('safe_time_hours', sa.Float(), nullable=True),
        sa.Column('recommended_start', sa.String(10), nullable=True),
        sa.Column('segments', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('actual_time_hours', sa.Float(), nullable=True),
        sa.Column('accuracy_percent', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Create indexes
    op.create_index('ix_gpx_files_user_id', 'gpx_files', ['user_id'])
    op.create_index('ix_predictions_user_id', 'predictions', ['user_id'])
    op.create_index('ix_predictions_gpx_file_id', 'predictions', ['gpx_file_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_predictions_gpx_file_id', 'predictions')
    op.drop_index('ix_predictions_user_id', 'predictions')
    op.drop_index('ix_gpx_files_user_id', 'gpx_files')

    # Drop tables
    op.drop_table('predictions')
    op.drop_table('gpx_files')
    op.drop_table('users')

    # Drop enums (PostgreSQL specific)
    op.execute('DROP TYPE IF EXISTS predictiontype')
    op.execute('DROP TYPE IF EXISTS experiencelevel')
    op.execute('DROP TYPE IF EXISTS backpackweight')
