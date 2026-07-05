from engine.requirement_engine.business_rule_resolver import BusinessRuleResolver
from engine.requirement_engine.database_resolver import DatabaseResolver
from engine.requirement_engine.models import RequirementAnalysis
from engine.requirement_engine.requirement_normalizer import RequirementNormalizer
from engine.requirement_engine.validator import RequirementValidator


def _analysis(requirement: str) -> RequirementAnalysis:
    payload = RequirementNormalizer().normalize(requirement)
    return RequirementValidator().validate(RequirementAnalysis.model_validate(payload))


def test_business_rule_resolver_returns_applicable_rules() -> None:
    analysis = _analysis(
        "garden ranking for assam ctc est season 2026 upto sale 26"
    )

    resolution = BusinessRuleResolver().resolve(analysis)
    rule_ids = {rule.rule_id for rule in resolution.applicable_rules}

    assert "BR-003" in rule_ids
    assert "BR-009" in rule_ids
    assert "BR-017" in rule_ids
    assert all(rule.applies_because for rule in resolution.applicable_rules)


def test_database_resolver_returns_sale_transaction_view() -> None:
    analysis = _analysis(
        "sale wise average price for assam orthodox season 2026 sale 20"
    )

    resolution = DatabaseResolver().resolve(analysis)
    object_names = {item.object_name for item in resolution.candidate_database_objects}

    assert "data-warehousing-prod.EasyReports.SaleTransactionView" in object_names


def test_orchestrator_context_resolution_is_visible() -> None:
    analysis = _analysis(
        "buyer wise purchase report for HUL season 2026 sale 14 to 26"
    )
    rule_resolution = BusinessRuleResolver().resolve(analysis)
    db_resolution = DatabaseResolver().resolve(analysis)

    assert rule_resolution.applicable_rules
    assert db_resolution.candidate_database_objects
