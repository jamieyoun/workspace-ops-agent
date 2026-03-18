"""Page endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Page, PageMetric, Issue, Recommendation
from app.schemas import PageResponse, PageMetricResponse, IssueResponse, RecommendationResponse

router = APIRouter(prefix="/pages", tags=["pages"])


@router.get("/{page_id}", response_model=PageResponse)
def get_page(page_id: int, db: Session = Depends(get_db)):
    """Get page by ID."""
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{page_id}/metrics", response_model=List[PageMetricResponse])
def list_page_metrics(page_id: int, db: Session = Depends(get_db)):
    """List metrics for a page."""
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    metrics = db.query(PageMetric).filter(PageMetric.page_id == page_id).all()
    return metrics


@router.get("/{page_id}/issues", response_model=List[IssueResponse])
def list_page_issues(page_id: int, db: Session = Depends(get_db)):
    """List issues for a page."""
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    issues = db.query(Issue).filter(Issue.page_id == page_id).all()
    return issues


@router.get("/{page_id}/recommendations", response_model=List[RecommendationResponse])
def list_page_recommendations(page_id: int, db: Session = Depends(get_db)):
    """List recommendations for a page (deduplicated by type + page_id)."""
    from app.utils import dedupe_recommendations

    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    recs = db.query(Recommendation).filter(Recommendation.page_id == page_id).all()
    return dedupe_recommendations(recs)
