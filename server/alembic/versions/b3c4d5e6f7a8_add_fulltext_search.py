"""enable pg_trgm and add functional GIN index for full-text search on profiles

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-23 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable trigram extension for fuzzy matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add a stored tsvector column. A GIN index on a plain column has no
    # IMMUTABLE restriction — only functional GIN index expressions require it.
    # Neon PostgreSQL (PG16) rejects to_tsvector() in a functional index because
    # the text→regconfig cast makes it STABLE, not IMMUTABLE.
    op.execute("""
        ALTER TABLE profiles
        ADD COLUMN IF NOT EXISTS search_tsv tsvector
    """)

    # Populate existing rows
    op.execute("""
        UPDATE profiles SET search_tsv = to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(bio, '') || ' ' ||
            coalesce(array_to_string(skills, ' '), '')
        )
    """)

    # GIN index on the plain stored column — no volatility constraint
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_profiles_fts
        ON profiles USING GIN (search_tsv)
    """)

    # Trigger to keep search_tsv fresh on every insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION profiles_search_tsv_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_tsv := to_tsvector('english',
                coalesce(NEW.title, '') || ' ' ||
                coalesce(NEW.bio, '') || ' ' ||
                coalesce(array_to_string(NEW.skills, ' '), '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS profiles_search_tsv_trigger ON profiles
    """)

    op.execute("""
        CREATE TRIGGER profiles_search_tsv_trigger
        BEFORE INSERT OR UPDATE ON profiles
        FOR EACH ROW EXECUTE FUNCTION profiles_search_tsv_update()
    """)

    # Trigram index on title for fuzzy fallback (handles typos like "develoer")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_profiles_title_trgm
        ON profiles USING GIN (title gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS profiles_search_tsv_trigger ON profiles")
    op.execute("DROP FUNCTION IF EXISTS profiles_search_tsv_update()")
    op.execute("DROP INDEX IF EXISTS ix_profiles_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_profiles_fts")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS search_tsv")
