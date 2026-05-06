"""
api/routers/reviews.py
POST /v1/reviews       — create or update a review
GET  /v1/reviews/{movie_id} — get the authenticated user's review for a movie
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.middleware.auth import get_current_user
from api.schemas.schemas import ReviewCreate, ReviewOut
from data.database import get_db
from data.models import Review, User

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


@router.post("", response_model=ReviewOut, status_code=status.HTTP_200_OK)
def upsert_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter_by(
        user_id=current_user.user_id, movie_id=payload.movie_id
    ).first()

    if review:
        review.review_text = payload.review_text
    else:
        review = Review(
            user_id=current_user.user_id,
            movie_id=payload.movie_id,
            review_text=payload.review_text,
        )
        db.add(review)

    db.commit()
    db.refresh(review)
    return review


@router.get("/{movie_id}", response_model=ReviewOut)
def get_review(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter_by(
        user_id=current_user.user_id, movie_id=movie_id
    ).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review found")
    return review
