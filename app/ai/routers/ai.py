from fastapi import APIRouter, Depends

from app.ai.schemas import (
    AIStatusResponse,
    AnomalyListResponse,
    InsightResponse,
    IntentExecuteRequest,
    IntentExecutionResponse,
    IntentPlan,
    IntentReviewRequest,
    ParseIntentRequest,
    RecommendationListResponse,
)
from app.ai.service import service
from app.auth import current_user
from app.models import OkResponse

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(current_user)])


@router.get("/status", response_model=AIStatusResponse)
async def status() -> AIStatusResponse:
    return service.status()


@router.get("/insights", response_model=InsightResponse)
async def insights() -> InsightResponse:
    return await service.insights()


@router.get("/recommendations", response_model=RecommendationListResponse)
async def recommendations() -> RecommendationListResponse:
    return await service.recommendations()


@router.get("/anomalies", response_model=AnomalyListResponse)
async def anomalies() -> AnomalyListResponse:
    return await service.anomalies()


@router.post("/intent/parse", response_model=IntentPlan)
async def parse_intent(
    request: ParseIntentRequest,
    username: str = Depends(current_user),
) -> IntentPlan:
    return await service.parse_intent(username, request.text)


@router.post("/intent/review", response_model=OkResponse)
async def review_intent(
    request: IntentReviewRequest,
    username: str = Depends(current_user),
) -> OkResponse:
    await service.review_intent(username, request.text, request.plan, request.approved)
    return OkResponse(detail="review recorded")


@router.post("/intent/execute", response_model=IntentExecutionResponse)
async def execute_intent(
    request: IntentExecuteRequest,
    username: str = Depends(current_user),
) -> IntentExecutionResponse:
    return await service.execute_intent(username, request)
