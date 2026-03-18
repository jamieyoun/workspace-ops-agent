"""SQLAlchemy ORM models for Notion-like workspace."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class Workspace(Base):
    """Workspace model."""

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    pages = relationship("Page", back_populates="workspace")
    issues = relationship("Issue", back_populates="workspace")
    recommendations = relationship("Recommendation", back_populates="workspace")
    agent_actions = relationship("AgentAction", back_populates="workspace")


class Page(Base):
    """Page model."""

    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content_markdown = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)

    workspace = relationship("Workspace", back_populates="pages")
    metrics = relationship("PageMetric", back_populates="page")
    issues = relationship("Issue", back_populates="page")
    recommendations = relationship("Recommendation", back_populates="page")


class PageMetric(Base):
    """Page metrics (word count, blocks, embeds, etc.)."""

    __tablename__ = "page_metrics"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    word_count = Column(Integer, default=0)
    block_count = Column(Integer, default=0)
    embed_count = Column(Integer, default=0)
    database_refs_count = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow)

    page = relationship("Page", back_populates="metrics")


class Issue(Base):
    """Issue model (problems detected in workspace)."""

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)
    type = Column(String(100), nullable=False)
    severity = Column(Integer, nullable=False)  # 1-5
    summary = Column(String(500), nullable=False)
    details_json = Column(Text, nullable=True)
    issue_key = Column(String(255), nullable=True, index=True)  # for upsert deduplication
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (CheckConstraint("severity >= 1 AND severity <= 5", name="ck_issue_severity"),)

    workspace = relationship("Workspace", back_populates="issues")
    page = relationship("Page", back_populates="issues")


class Recommendation(Base):
    """Recommendation model (suggested improvements)."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)
    type = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False)  # 1-5
    title = Column(String(500), nullable=False)
    rationale = Column(Text, nullable=True)
    proposed_changes_json = Column(Text, nullable=True)
    why_this_matters = Column(Text, nullable=True)
    risk_tradeoff = Column(Text, nullable=True)
    expected_impact = Column(Text, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="proposed",
    )  # proposed, approved, applied, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "priority >= 1 AND priority <= 5",
            name="ck_recommendation_priority",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'applied', 'dismissed')",
            name="ck_recommendation_status",
        ),
    )

    workspace = relationship("Workspace", back_populates="recommendations")
    page = relationship("Page", back_populates="recommendations")
    agent_actions = relationship("AgentAction", back_populates="recommendation")


class AgentAction(Base):
    """Agent or user action log."""

    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    action_type = Column(String(100), nullable=False)
    actor = Column(String(20), nullable=False)  # agent | user
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("actor IN ('agent', 'user')", name="ck_agent_action_actor"),
    )

    workspace = relationship("Workspace", back_populates="agent_actions")
    recommendation = relationship("Recommendation", back_populates="agent_actions")
