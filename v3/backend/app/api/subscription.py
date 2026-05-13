from fastapi import APIRouter, Depends
from ..modules.adapters import get_default_service_registry
from ..modules.dependencies import get_current_user
from ..modules.messages import envelope
from ..schemas.request import SubscriptionQuoteRequest, SubscriptionActivateRequest
from ..schemas.response import (
    PlanResponseEnvelope,
    PlanLimitsResponseEnvelope,
    SubscriptionCatalogResponseEnvelope,
    SubscriptionQuoteResponseEnvelope,
    SubscriptionActivateResponseEnvelope,
)

router = APIRouter()
services = get_default_service_registry()


@router.get("/plan/me", response_model=PlanResponseEnvelope)
def get_my_plan(user=Depends(get_current_user)):
    return envelope(services.commercial.get_plan_me(user["username"]), message_id="MSG-1000")


@router.get("/plan/limits", response_model=PlanLimitsResponseEnvelope)
def get_plan_limits(user=Depends(get_current_user)):
    return envelope(services.commercial.get_plan_limits(user["username"]), message_id="MSG-1000")


@router.get("/subscription/catalog", response_model=SubscriptionCatalogResponseEnvelope)
def get_subscription_catalog_endpoint(user=Depends(get_current_user)):
    return envelope(services.commercial.get_subscription_catalog(), message_id="MSG-1000")


@router.post("/subscription/quote", response_model=SubscriptionQuoteResponseEnvelope)
def get_subscription_quote(request: SubscriptionQuoteRequest, user=Depends(get_current_user)):
    quote = services.commercial.quote_subscription(
        class_names=request.class_names,
        promo_code=request.promo_code,
        auto_renew=request.auto_renew,
    )
    return envelope(quote, message_id="MSG-1000")


@router.post("/subscription/activate", response_model=SubscriptionActivateResponseEnvelope)
def activate_subscription_endpoint(request: SubscriptionActivateRequest, user=Depends(get_current_user)):
    result = services.commercial.activate_subscription(
        user_id=user["username"],
        class_names=request.class_names,
        promo_code=request.promo_code,
        auto_renew=request.auto_renew,
        payment_reference=request.payment_reference,
    )
    return envelope(result, message_id="MSG-1000")
