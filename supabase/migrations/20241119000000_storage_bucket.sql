-- Create storage bucket for datasets
-- Tables are created via SQLModel in Python, this only sets up storage

INSERT INTO storage.buckets (id, name, public)
VALUES ('datasets', 'datasets', true)
ON CONFLICT (id) DO NOTHING;
