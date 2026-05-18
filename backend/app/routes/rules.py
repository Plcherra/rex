from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_rule_service
from app.models.personal_rule import (
    PersonalRuleCreateRequest,
    PersonalRuleResponse,
    PersonalRuleUpdateRequest,
    RuleStatus,
    RuleType,
)
from app.services.rule_service import RuleService, RuleServiceError


router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[PersonalRuleResponse])
async def list_rules(
    rule_type: Optional[RuleType] = Query(default=None),
    status: Optional[RuleStatus] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    rule_service: RuleService = Depends(get_rule_service),
) -> list[PersonalRuleResponse]:
    try:
        rules = await rule_service.list_rules(
            rule_type=rule_type,
            status=status,
            active=active,
            limit=limit,
        )
    except RuleServiceError as error:
        raise _rule_http_error(error) from error

    return [PersonalRuleResponse(**rule) for rule in rules]


@router.post("", response_model=PersonalRuleResponse, status_code=201)
async def create_rule(
    request: PersonalRuleCreateRequest,
    rule_service: RuleService = Depends(get_rule_service),
) -> PersonalRuleResponse:
    try:
        rule = await rule_service.create_rule(request)
    except RuleServiceError as error:
        raise _rule_http_error(error) from error

    return PersonalRuleResponse(**rule)


@router.patch("/{rule_id}", response_model=PersonalRuleResponse)
async def update_rule(
    rule_id: str,
    request: PersonalRuleUpdateRequest,
    rule_service: RuleService = Depends(get_rule_service),
) -> PersonalRuleResponse:
    try:
        rule = await rule_service.update_rule(rule_id, request)
    except RuleServiceError as error:
        raise _rule_http_error(error) from error

    return PersonalRuleResponse(**rule)


@router.delete("/{rule_id}", status_code=204)
async def deactivate_rule(
    rule_id: str,
    rule_service: RuleService = Depends(get_rule_service),
) -> Response:
    try:
        await rule_service.deactivate_rule(rule_id)
    except RuleServiceError as error:
        raise _rule_http_error(error) from error

    return Response(status_code=204)


def _rule_http_error(error: RuleServiceError):
    from fastapi import HTTPException

    return HTTPException(status_code=error.status_code, detail=error.detail)
