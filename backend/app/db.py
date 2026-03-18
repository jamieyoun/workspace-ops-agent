"""Database configuration and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import get_settings

engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Add missing columns for schema changes (no migration system)."""
    with engine.connect() as conn:
        # issues.issue_key
        result = conn.execute(text("PRAGMA table_info(issues)"))
        columns = [row[1] for row in result]
        if columns and "issue_key" not in columns:
            conn.execute(text("ALTER TABLE issues ADD COLUMN issue_key VARCHAR(255)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_issues_issue_key ON issues (issue_key)"))
            conn.commit()

        # recommendations.why_this_matters, risk_tradeoff, expected_impact
        result = conn.execute(text("PRAGMA table_info(recommendations)"))
        rec_columns = [row[1] for row in result]
        if rec_columns:
            for col in ("why_this_matters", "risk_tradeoff", "expected_impact"):
                if col not in rec_columns:
                    conn.execute(text(f"ALTER TABLE recommendations ADD COLUMN {col} TEXT"))
            conn.commit()

        # pages.archived_at
        result = conn.execute(text("PRAGMA table_info(pages)"))
        page_columns = [row[1] for row in result]
        if page_columns and "archived_at" not in page_columns:
            conn.execute(text("ALTER TABLE pages ADD COLUMN archived_at DATETIME"))
            conn.commit()


def init_db():
    """Create all tables and run migrations."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()
