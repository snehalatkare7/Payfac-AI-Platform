"""API routes for the Fraud Analysis platform."""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from app.api.schemas import (
    AnalyzeTransactionRequest,
    FraudAlertResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    HealthResponse,
    MerchantRiskProfileResponse,
    FeedbackRequest,
)
from app.models import Transaction

logger = logging.getLogger(__name__)

router = APIRouter()


def get_orchestrator():
    """Dependency injection for the orchestrator agent."""
    from app.main import app_state
    return app_state["orchestrator"]


def get_memory():
    """Dependency injection for the memory manager."""
    from app.main import app_state
    return app_state["memory"]


# ── Analysis Endpoints ────────────────────────────────────────────────

@router.post(
    "/v1/analyze",
    response_model=FraudAlertResponse,
    summary="Analyze a transaction for fraud",
    tags=["Analysis"],
)
async def analyze_transaction(
    request: AnalyzeTransactionRequest,
    orchestrator=Depends(get_orchestrator),
):
    """
    Submit a single transaction for multi-agent fraud analysis.

    The analysis pipeline:
    1. Fraud Detection Agent analyzes for fraud patterns (Agentic RAG)
    2. Compliance Agent checks card brand rules
    3. Risk Scoring Agent computes composite risk score
    4. Investigation Agent conducts deep-dive (if risk > 60)
    """
    try:
        transaction = Transaction(
            transaction_id=request.transaction_id,
            merchant_id=request.merchant_id,
            merchant_name=request.merchant_name,
            merchant_category_code=request.merchant_category_code,
            amount_cents=request.amount_cents,
            currency=request.currency,
            card_brand=request.card_brand,
            card_last_four=request.card_last_four,
            card_bin=request.card_bin,
            is_card_present=request.is_card_present,
            entry_mode=request.entry_mode,
            ip_address=request.ip_address,
            billing_country=request.billing_country,
            shipping_country=request.shipping_country,
            customer_id=request.customer_id,
            is_recurring=request.is_recurring,
        )

        alert = await orchestrator.analyze(transaction)

        return FraudAlertResponse(
            alert_id=alert.alert_id,
            merchant_id=alert.merchant_id,
            transaction_id=alert.transaction_id,
            fraud_type=alert.fraud_type.value,
            risk_level=alert.risk_level.value,
            risk_score=alert.risk_score,
            summary=alert.summary,
            evidence=alert.evidence,
            recommendations=alert.recommendations,
            confidence=alert.confidence,
            analyzed_by_agents=alert.analyzed_by_agents,
            analyzed_at=alert.analyzed_at,
        )

    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post(
    "/v1/analyze/batch",
    response_model=BatchAnalyzeResponse,
    summary="Analyze multiple transactions for fraud",
    tags=["Analysis"],
)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    orchestrator=Depends(get_orchestrator),
):
    """Submit a batch of transactions for fraud analysis."""
    start_time = time.time()
    alerts = []
    high_risk_count = 0

    for txn_request in request.transactions:
        try:
            transaction = Transaction(
                transaction_id=txn_request.transaction_id,
                merchant_id=txn_request.merchant_id,
                merchant_name=txn_request.merchant_name,
                merchant_category_code=txn_request.merchant_category_code,
                amount_cents=txn_request.amount_cents,
                currency=txn_request.currency,
                card_brand=txn_request.card_brand,
                card_last_four=txn_request.card_last_four,
                card_bin=txn_request.card_bin,
                is_card_present=txn_request.is_card_present,
                entry_mode=txn_request.entry_mode,
            )
            alert = await orchestrator.analyze(transaction)
            alerts.append(FraudAlertResponse(
                alert_id=alert.alert_id,
                merchant_id=alert.merchant_id,
                transaction_id=alert.transaction_id,
                fraud_type=alert.fraud_type.value,
                risk_level=alert.risk_level.value,
                risk_score=alert.risk_score,
                summary=alert.summary,
                evidence=alert.evidence,
                recommendations=alert.recommendations,
                confidence=alert.confidence,
                analyzed_by_agents=alert.analyzed_by_agents,
                analyzed_at=alert.analyzed_at,
            ))
            if alert.risk_score > 60:
                high_risk_count += 1
        except Exception as e:
            logger.error(
                "Batch analysis failed for txn %s: %s",
                txn_request.transaction_id, e,
            )

    elapsed_ms = (time.time() - start_time) * 1000

    return BatchAnalyzeResponse(
        total=len(request.transactions),
        alerts=alerts,
        high_risk_count=high_risk_count,
        processing_time_ms=elapsed_ms,
    )


# ── Merchant Endpoints ───────────────────────────────────────────────

@router.get(
    "/v1/merchants/{merchant_id}/risk-profile",
    response_model=MerchantRiskProfileResponse,
    summary="Get merchant risk profile",
    tags=["Merchants"],
)
async def get_merchant_profile(
    merchant_id: str,
    memory=Depends(get_memory),
):
    """Retrieve the accumulated risk profile for a merchant."""
    profile = await memory.long_term.get_merchant_profile(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Merchant {merchant_id} not found")

    return MerchantRiskProfileResponse(
        merchant_id=profile.merchant_id,
        merchant_name=profile.merchant_name,
        mcc=profile.mcc,
        historical_fraud_count=profile.historical_fraud_count,
        chargeback_ratio=profile.chargeback_ratio,
        average_risk_score=profile.average_risk_score,
        known_fraud_types=[ft.value for ft in profile.known_fraud_types],
        is_high_risk=profile.is_high_risk,
        last_review_date=profile.last_review_date,
    )


@router.get(
    "/v1/merchants/high-risk",
    response_model=list[MerchantRiskProfileResponse],
    summary="List high-risk merchants",
    tags=["Merchants"],
)
async def list_high_risk_merchants(memory=Depends(get_memory)):
    """Retrieve all merchants currently flagged as high risk."""
    profiles = await memory.long_term.get_high_risk_merchants()
    return [
        MerchantRiskProfileResponse(
            merchant_id=p.merchant_id,
            merchant_name=p.merchant_name,
            mcc=p.mcc,
            historical_fraud_count=p.historical_fraud_count,
            chargeback_ratio=p.chargeback_ratio,
            average_risk_score=p.average_risk_score,
            known_fraud_types=[ft.value for ft in p.known_fraud_types],
            is_high_risk=p.is_high_risk,
            last_review_date=p.last_review_date,
        )
        for p in profiles
    ]


# ── Feedback Endpoint ─────────────────────────────────────────────────

@router.post(
    "/v1/feedback",
    summary="Provide feedback on analysis decision",
    tags=["Feedback"],
)
async def submit_feedback(
    request: FeedbackRequest,
    memory=Depends(get_memory),
):
    """
    Submit feedback on a previous fraud analysis decision.

    This feedback is stored in long-term memory and used to
    improve future analysis accuracy (feedback loop).
    """
    try:
        await memory.long_term.update_decision_feedback(
            decision_id=request.decision_id,
            was_correct=request.was_correct,
            feedback_notes=request.feedback_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "feedback_recorded", "decision_id": request.decision_id}


# ── Health Check ──────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health_check():
    """Check the health of all platform components."""
    from app.main import app_state

    neondb_ok = False
    redis_ok = False
    kafka_ok = False

    try:
        neondb = app_state.get("neondb")
        if neondb:
            await neondb.execute_query("SELECT 1")
            neondb_ok = True
    except Exception:
        pass

    try:
        redis_client = app_state.get("redis")
        if redis_client:
            await redis_client.client.ping()
            redis_ok = True
    except Exception:
        pass

    try:
        kafka = app_state.get("kafka_producer")
        if kafka:
            kafka_ok = True  # Producer doesn't have a ping method
    except Exception:
        pass

    status = "healthy" if all([neondb_ok, redis_ok, kafka_ok]) else "degraded"

    return HealthResponse(
        status=status,
        version="1.0.0",
        neondb_connected=neondb_ok,
        redis_connected=redis_ok,
        kafka_connected=kafka_ok,
    )
