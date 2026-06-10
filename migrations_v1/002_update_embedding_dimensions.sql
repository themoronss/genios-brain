-- Update embedding dimensions from 1536 to 3072 for gemini-embedding-001 model

ALTER TABLE contacts ALTER COLUMN embedding TYPE vector(3072);
ALTER TABLE interactions ALTER COLUMN embedding TYPE vector(3072);
