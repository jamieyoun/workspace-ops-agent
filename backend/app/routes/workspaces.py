"""Workspace endpoints."""

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analysis.pipeline import run_analysis
from app.analysis.scoring import compute_workspace_score
from app.analysis_cache import get_cached, invalidate_workspace, set_cached
from app.agents.ops_agent import generate_recommendations
from app.db import get_db
from app.metrics_store import record_last_run
from app.models import Workspace, Page, Issue, Recommendation, AgentAction
from app.rate_limit import check_rate_limit
from app.schemas import (
    WorkspaceResponse,
    WorkspaceWithStats,
    WorkspaceStats,
    IssueResponse,
    WorkspaceScoreResponse,
    SubscoreResponse,
    AnalyzeResponse,
    GenerateRecommendationsResponse,
    RecommendationResponse,
    AuditActionResponse,
    PageResponse,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _get_workspace_stats(db: Session, workspace_id: int) -> WorkspaceStats:
    """Compute basic stats for a workspace."""
    page_count = db.query(func.count(Page.id)).filter(Page.workspace_id == workspace_id).scalar() or 0
    issue_count = db.query(func.count(Issue.id)).filter(Issue.workspace_id == workspace_id).scalar() or 0
    open_issue_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.workspace_id == workspace_id, Issue.resolved_at.is_(None))
        .scalar()
        or 0
    )
    recommendation_count = (
        db.query(func.count(Recommendation.id))
        .filter(Recommendation.workspace_id == workspace_id)
        .scalar()
        or 0
    )
    proposed_recommendation_count = (
        db.query(func.count(Recommendation.id))
        .filter(Recommendation.workspace_id == workspace_id, Recommendation.status == "proposed")
        .scalar()
        or 0
    )
    return WorkspaceStats(
        page_count=page_count,
        issue_count=issue_count,
        open_issue_count=open_issue_count,
        recommendation_count=recommendation_count,
        proposed_recommendation_count=proposed_recommendation_count,
    )


@router.get("", response_model=List[WorkspaceWithStats])
def list_workspaces(db: Session = Depends(get_db)):
    """List all workspaces with basic stats."""
    workspaces = db.query(Workspace).all()
    result = []
    for ws in workspaces:
        stats = _get_workspace_stats(db, ws.id)
        result.append(
            WorkspaceWithStats(
                id=ws.id,
                name=ws.name,
                created_at=ws.created_at,
                stats=stats,
            )
        )
    return result


@router.get("/{workspace_id}", response_model=WorkspaceWithStats)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """Get workspace by ID with stats."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    stats = _get_workspace_stats(db, workspace.id)
    return WorkspaceWithStats(
        id=workspace.id,
        name=workspace.name,
        created_at=workspace.created_at,
        stats=stats,
    )


@router.post("/{workspace_id}/analyze", response_model=AnalyzeResponse)
def analyze_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """Run analysis pipeline: compute metrics, detect issues, upsert to DB."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    result = run_analysis(workspace_id, db)
    invalidate_workspace(workspace_id)
    db.add(
        AgentAction(
            workspace_id=workspace_id,
            recommendation_id=None,
            action_type="run_analysis",
            actor="agent",
            payload_json=json.dumps(result),
        )
    )
    db.commit()
    record_last_run("analyze")
    return result


@router.get("/{workspace_id}/issues", response_model=List[IssueResponse])
def list_workspace_issues(workspace_id: int, db: Session = Depends(get_db)):
    """List issues for a workspace."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    cached = get_cached(workspace_id, "issues")
    if cached is not None:
        return cached
    issues = db.query(Issue).filter(Issue.workspace_id == workspace_id).all()
    set_cached(workspace_id, "issues", issues)
    return issues


def _get_last_analysis_at(db: Session, workspace_id: int):
    """Get timestamp of most recent run_analysis action for workspace."""
    action = (
        db.query(AgentAction)
        .filter(AgentAction.workspace_id == workspace_id, AgentAction.action_type == "run_analysis")
        .order_by(AgentAction.created_at.desc())
        .first()
    )
    return action.created_at if action else None


@router.get("/{workspace_id}/score", response_model=WorkspaceScoreResponse)
def get_workspace_score(workspace_id: int, db: Session = Depends(get_db)):
    """Return workspace health score with subscores and explanations."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    cached = get_cached(workspace_id, "score")
    if cached is not None:
        return cached
    page_count = db.query(func.count(Page.id)).filter(Page.workspace_id == workspace_id).scalar() or 0
    issues = db.query(Issue).filter(Issue.workspace_id == workspace_id).all()
    issue_dicts = [
        {"type": i.type, "resolved_at": i.resolved_at}
        for i in issues
    ]
    score = compute_workspace_score(page_count, issue_dicts)
    last_analysis_at = _get_last_analysis_at(db, workspace_id)
    result = WorkspaceScoreResponse(
        overall=score.overall,
        subscores=[
            SubscoreResponse(name=s.name, score=s.score, weight=s.weight, explanation=s.explanation)
            for s in score.subscores
        ],
        issue_count=score.issue_count,
        open_issue_count=score.open_issue_count,
        last_analysis_at=last_analysis_at,
    )
    set_cached(workspace_id, "score", result)
    return result


@router.post("/{workspace_id}/recommendations/generate", response_model=GenerateRecommendationsResponse)
def generate_workspace_recommendations(workspace_id: int, db: Session = Depends(get_db)):
    """Generate recommendations from issues using Ops Agent (OpenAI or heuristic fallback)."""
    if not check_rate_limit(workspace_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    page_count = db.query(func.count(Page.id)).filter(Page.workspace_id == workspace_id).scalar() or 0
    open_issues = (
        db.query(Issue)
        .filter(Issue.workspace_id == workspace_id, Issue.resolved_at.is_(None))
        .order_by(Issue.severity)
        .limit(15)
        .all()
    )
    issue_dicts = [
        {
            "type": i.type,
            "severity": i.severity,
            "summary": i.summary,
            "page_id": i.page_id,
            "details_json": i.details_json,
        }
        for i in open_issues
    ]
    recs, source = generate_recommendations(workspace.name, page_count, issue_dicts)
    created = []
    for r in recs:
        # Skip if duplicate: same type + page_id already exists (proposed or approved)
        key = (r.type, r.page_id)
        existing = (
            db.query(Recommendation)
            .filter(
                Recommendation.workspace_id == workspace_id,
                Recommendation.type == r.type,
                Recommendation.page_id == r.page_id,
                Recommendation.status.in_(["proposed", "approved"]),
            )
            .first()
        )
        if existing:
            continue
        rec = Recommendation(
            workspace_id=workspace_id,
            page_id=r.page_id,
            type=r.type,
            priority=r.priority,
            title=r.title,
            rationale=r.rationale,
            proposed_changes_json=json.dumps(r.proposed_changes_json),
            status="proposed",
        )
        db.add(rec)
        created.append(rec)
    db.commit()
    for rec in created:
        db.refresh(rec)
    # Log agent action
    db.add(
        AgentAction(
            workspace_id=workspace_id,
            recommendation_id=created[0].id if created else None,
            action_type="generate_recommendations",
            actor="agent",
            payload_json=json.dumps({"count": len(created), "source": source}),
        )
    )
    db.commit()
    record_last_run("generate_recommendations")
    return GenerateRecommendationsResponse(count=len(created), source=source)


@router.get("/{workspace_id}/pages", response_model=List[PageResponse])
def list_workspace_pages(workspace_id: int, db: Session = Depends(get_db)):
    """List pages in a workspace."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    pages = db.query(Page).filter(Page.workspace_id == workspace_id).all()
    return pages


@router.get("/{workspace_id}/recommendations", response_model=List[RecommendationResponse])
def list_workspace_recommendations(workspace_id: int, db: Session = Depends(get_db)):
    """List recommendations for a workspace (deduplicated by type + page_id)."""
    from app.utils import dedupe_recommendations

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    recs = db.query(Recommendation).filter(Recommendation.workspace_id == workspace_id).all()
    return dedupe_recommendations(recs)


@router.get("/{workspace_id}/audit", response_model=List[AuditActionResponse])
def list_workspace_audit(workspace_id: int, db: Session = Depends(get_db)):
    """List audit log (agent + user actions) for a workspace."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    actions = (
        db.query(AgentAction)
        .filter(AgentAction.workspace_id == workspace_id)
        .order_by(AgentAction.created_at.desc())
        .all()
    )
    return actions
