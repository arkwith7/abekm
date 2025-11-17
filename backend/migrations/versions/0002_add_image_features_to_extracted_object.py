"""Add image features to doc_extracted_object

Revision ID: 0002_add_image_features
Revises: 0001_multimodal_schema
Create Date: 2025-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_add_image_features'
down_revision = '0001_multimodal_schema'  # Assumes multimodal schema exists
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add image-specific feature columns to doc_extracted_object table."""
    # Add image width/height/phash columns for IMAGE objects
    op.add_column('doc_extracted_object', sa.Column('image_width', sa.Integer(), nullable=True))
    op.add_column('doc_extracted_object', sa.Column('image_height', sa.Integer(), nullable=True))
    op.add_column('doc_extracted_object', sa.Column('phash', sa.String(length=32), nullable=True))
    
    # Create index on phash for similarity queries
    op.create_index('idx_doc_extracted_object_phash', 'doc_extracted_object', ['phash'])
    
    # Create composite index for image objects with dimensions
    op.create_index(
        'idx_doc_extracted_object_image_features', 
        'doc_extracted_object', 
        ['object_type', 'image_width', 'image_height'],
        postgresql_where=sa.text("object_type = 'IMAGE'")
    )


def downgrade() -> None:
    """Remove image feature columns from doc_extracted_object table."""
    # Drop indexes first
    op.drop_index('idx_doc_extracted_object_image_features', table_name='doc_extracted_object')
    op.drop_index('idx_doc_extracted_object_phash', table_name='doc_extracted_object')
    
    # Drop columns
    op.drop_column('doc_extracted_object', 'phash')
    op.drop_column('doc_extracted_object', 'image_height')
    op.drop_column('doc_extracted_object', 'image_width')