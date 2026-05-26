import uuid
import logging
from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models.appreciation import Appreciation
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.ai.fraud_prompt import analyze_appreciations

logger = logging.getLogger(__name__)

_SCORE_PENALTY = {"medium": 7, "high": 15}


async def run_fraud_detection(user_id: uuid.UUID) -> None:
    """Analyze all appreciations for a user and update CredibilityScore fraud fields.

    Runs AFTER compute_and_save_score in the background task queue so that the
    base score exists before the fraud penalty is applied.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Appreciation)
                .where(Appreciation.to_user_id == user_id)
                .order_by(Appreciation.created_at)
            )
            rows = result.scalars().all()

            # Need at least 2 reviews to detect cross-review patterns
            if len(rows) < 2:
                return

            appreciation_data = [
                {
                    "raw_feedback": r.raw_feedback,
                    "skill_rating": r.skill_rating or 5.0,
                    "communication_rating": r.communication_rating or 5.0,
                    "reliability_rating": r.reliability_rating or 5.0,
                }
                for r in rows
            ]

            try:
                fraud_result = await analyze_appreciations(appreciation_data)
            except Exception:
                logger.warning("Fraud AI unavailable for user %s, defaulting to medium risk", user_id)
                fraud_result = {"fraud_risk": "medium", "flags": ["AI analysis unavailable — manual review recommended"]}
            risk_level = fraud_result["fraud_risk"]
            flags = fraud_result["flags"]

            score_result = await db.execute(
                select(CredibilityScore).where(CredibilityScore.user_id == user_id)
            )
            score_row = score_result.scalar_one_or_none()

            if not score_row:
                return

            penalty = _SCORE_PENALTY.get(risk_level, 0)
            score_row.score = max(0, score_row.score - penalty)
            score_row.fraud_risk = FraudRisk(risk_level)
            score_row.fraud_flags = flags

            await db.commit()
            logger.info(
                "Fraud detection user=%s risk=%s flags=%d penalty=%d new_score=%d",
                user_id, risk_level, len(flags), penalty, score_row.score,
            )

        except Exception:
            logger.exception("Fraud detection failed for user %s", user_id)
            await db.rollback()
