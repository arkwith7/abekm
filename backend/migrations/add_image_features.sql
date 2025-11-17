-- D. Add image feature columns to doc_extracted_object table
-- Migration: Add image_width, image_height, phash columns

-- Add columns
ALTER TABLE doc_extracted_object 
  ADD COLUMN IF NOT EXISTS image_width INTEGER,
  ADD COLUMN IF NOT EXISTS image_height INTEGER,
  ADD COLUMN IF NOT EXISTS phash VARCHAR(32);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_doc_extracted_object_phash 
  ON doc_extracted_object (phash);

CREATE INDEX IF NOT EXISTS idx_doc_extracted_object_image_features 
  ON doc_extracted_object (object_type, image_width, image_height)
  WHERE object_type = 'IMAGE';

-- Add comments for documentation
COMMENT ON COLUMN doc_extracted_object.image_width IS 'Width in pixels for IMAGE objects';
COMMENT ON COLUMN doc_extracted_object.image_height IS 'Height in pixels for IMAGE objects';
COMMENT ON COLUMN doc_extracted_object.phash IS 'Perceptual hash for similarity detection (IMAGE objects)';