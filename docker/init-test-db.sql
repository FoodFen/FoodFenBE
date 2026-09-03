-- Runs once, on first initialisation of the data volume.
-- The test suite drops and recreates its schema, so it must not share a
-- database with development data or with the Alembic-managed schema.
CREATE DATABASE foodfen_test;
