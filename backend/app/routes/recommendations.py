"""Recommendation endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.apply import apply_recommendation
from app.agents.ops_agent import explain_recommendation
from app.db import get_db
from app.models import Recommendation, AgentAction
from app.schemas import (
    RecommendationResponse,
    RecommendationExplainResponse,
    RecommendationStatusResponse,
    ApplyRecommendationRequest,
    ApplyRecommendationResponse,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _log_user_action(
    db: Session,
    workspace_id: int,
    recommendation_id: int,
    action_type: str,
    payload: dict,
):
    db.add(
        AgentAction(
            workspace_id=workspace_id,
            recommendation_id=recommendation_id,
            action_type=action_type,
            actor="user",
            payload_json=json.dumps(payload),
        )
    )


@router.post("/{recommendation_id}/explain", response_model=RecommendationExplainResponse)
def explain_recommendation_endpoint(recommendation_id: int, db: Session = Depends(get_db)):
    """Generate and store admin-friendly explanation for a recommendation."""
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    expl, source = explain_recommendation(rec.type, rec.title, rec.rationale)
    rec.why_this_matters = expl.why_this_matters
    rec.risk_tradeoff = expl.risk_tradeoff
    rec.expected_impact = expl.expected_impact
    db.commit()
    db.refresh(rec)
    db.add(
        AgentAction(
            workspace_id=rec.workspace_id,
            recommendation_id=rec.id,
            action_type="explain_recommendation",
            actor="agent",
            payload_json=json.dumps({"source": source}),
        )
    )
    db.commit()
    return RecommendationExplainResponse(
        why_this_matters=expl.why_this_matters,
        risk_tradeoff=expl.risk_tradeoff,
        expected_impact=expl.expected_impact,
        source=source,
    )


@router.post("/{recommendation_id}/approve", response_model=RecommendationStatusResponse)
def approve_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Approve a proposed recommendation (status -> approved)."""
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status != "proposed":
        raise HTTPException(status_code=400, detail=f"Cannot approve: status is {rec.status}")
    rec.status = "approved"
    _log_user_action(db, rec.workspace_id, rec.id, "approve", {"from": "proposed"})
    db.commit()
    db.refresh(rec)
    return RecommendationStatusResponse(id=rec.id, status=rec.status)


@router.post("/{recommendation_id}/dismiss", response_model=RecommendationStatusResponse)
def dismiss_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Dismiss a recommendation (status -> dismissed)."""
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status not in ("proposed", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot dismiss: status is {rec.status}")
    prev = rec.status
    rec.status = "dismissed"
    _log_user_action(db, rec.workspace_id, rec.id, "dismiss", {"previous": prev})
    db.commit()
    db.refresh(rec)
    return RecommendationStatusResponse(id=rec.id, status=rec.status)


@router.post("/{recommendation_id}/apply", response_model=ApplyRecommendationResponse)
def apply_recommendation_endpoint(
    recommendation_id: int,
    body: ApplyRecommendationRequest = ApplyRecommendationRequest(),
    db: Session = Depends(get_db),
):
    """Apply a recommendation's effect. Idempotent: applying twice does nothing."""
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status == "applied":
        return ApplyRecommendationResponse(applied=False, reason="Already applied", idempotent=True)
    if rec.status not in ("proposed", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot apply: status is {rec.status}")
    payload = body.model_dump(exclude_none=True)
    result = apply_recommendation(db, rec, payload)
    _log_user_action(db, rec.workspace_id, rec.id, "apply", {"result": result})
    db.commit()
    db.refresh(rec)
    return ApplyRecommendationResponse(
        applied=result.get("applied", False),
        reason=result.get("reason"),
        idempotent=result.get("idempotent"),
        new_page_id=result.get("new_page_id"),
    )
