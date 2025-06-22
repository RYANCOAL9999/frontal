-- init.sql

CREATE TABLE IF NOT EXISTS crop_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    image_base64 TEXT NOT NULL,
    landmarks_json JSONB NOT NULL,
    segmentation_map_base64 TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    svg_base64 TEXT, 
    mask_contours_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_crop_jobs_status ON crop_jobs (status);

CREATE INDEX IF NOT EXISTS idx_crop_jobs_created_at ON crop_jobs (created_at);