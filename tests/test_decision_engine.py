from engine.requirement_engine.decision_engine import DecisionEngine
from engine.requirement_engine.business_rule_resolver import BusinessRuleResolver
from engine.requirement_engine.database_resolver import DatabaseResolver
from engine.requirement_engine.models import (
    BusinessRuleReference,
    BusinessRuleStatus,
    CandidateDatabaseObject,
    ClarificationQuestion,
    DatabaseObjectType,
    DecisionStatus,
    KnownInformation,
    QuestionPriority,
    RequirementAnalysis,
    RequirementFieldStatus,
)
from engine.requirement_engine.requirement_normalizer import RequirementNormalizer
from engine.requirement_engine.validator import RequirementValidator


def _complete_known_information() -> KnownInformation:
    return KnownInformation(
        season=2026,
        sale_range="sale 14 to 26",
        area="AS",
        category="CTC",
        metrics=["average price"],
        output_grain="garden-wise",
    )


def _business_rule() -> BusinessRuleReference:
    return BusinessRuleReference(
        rule_id="BR-006",
        name="Average Price",
        file_path="knowledge/business/BR-006_AveragePrice.md",
        status=BusinessRuleStatus.DOCUMENTED,
        relevance="Metric requires rule: average price",
    )


def _database_object() -> CandidateDatabaseObject:
    return CandidateDatabaseObject(
        object_name="data-warehousing-prod.EasyReports.SaleTransactionView",
        object_type=DatabaseObjectType.VIEW,
        purpose="Primary auction sale transaction source",
        confidence=RequirementFieldStatus.PROVIDED,
    )


def _analysis(
    *,
    known_information: KnownInformation | None = None,
    confidence_score: float = 0.95,
    business_rules: list[BusinessRuleReference] | None = None,
    database_objects: list[CandidateDatabaseObject] | None = None,
    clarification_questions: list[ClarificationQuestion] | None = None,
) -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Test requirement",
        known_information=known_information or _complete_known_information(),
        clarification_questions=clarification_questions or [],
        business_rules=business_rules if business_rules is not None else [_business_rule()],
        candidate_database_objects=(
            database_objects if database_objects is not None else [_database_object()]
        ),
        metadata={"confidence_score": confidence_score},
    )


def _resolved_offline_analysis(requirement: str) -> RequirementAnalysis:
    payload = RequirementNormalizer().normalize(requirement)
    analysis = RequirementAnalysis.model_validate(payload)
    analysis = RequirementValidator().validate(analysis)
    rule_resolution = BusinessRuleResolver().resolve(analysis)
    database_resolution = DatabaseResolver().resolve(analysis)
    return analysis.model_copy(
        update={
            "business_rules": [
                BusinessRuleReference(
                    rule_id=rule.rule_id,
                    name=rule.name,
                    file_path=rule.file_path,
                    status=BusinessRuleStatus.DOCUMENTED,
                    relevance="; ".join(rule.applies_because),
                )
                for rule in rule_resolution.applicable_rules
            ],
            "candidate_database_objects": (
                database_resolution.candidate_database_objects
            ),
        },
        deep=True,
    )


def test_missing_category_blocks_sql() -> None:
    known = _complete_known_information().model_copy(update={"category": None})
    validated = RequirementValidator().validate(_analysis(known_information=known))

    result = DecisionEngine().decide(validated)

    assert result.sql_generation_allowed is False
    assert result.decision_status == DecisionStatus.SQL_BLOCKED
    assert "Category or tea type is missing" in result.decision_reason


def test_low_starting_confidence_is_lifted_when_complete() -> None:
    result = DecisionEngine().decide(_analysis(confidence_score=0.20))

    assert result.sql_generation_allowed is True
    assert result.decision_status == DecisionStatus.SQL_ALLOWED
    assert result.metadata["confidence_score"] >= 0.85


def test_missing_database_objects_blocks_sql() -> None:
    result = DecisionEngine().decide(_analysis(database_objects=[]))

    assert result.sql_generation_allowed is False
    assert result.decision_status == DecisionStatus.SQL_BLOCKED
    assert "No candidate database objects" in result.decision_reason


def test_missing_business_rules_blocks_sql() -> None:
    result = DecisionEngine().decide(_analysis(business_rules=[]))

    assert result.sql_generation_allowed is False
    assert result.decision_status == DecisionStatus.SQL_BLOCKED
    assert "No applicable business rules" in result.decision_reason


def test_complete_high_confidence_requirement_allows_sql() -> None:
    result = DecisionEngine().decide(_analysis(confidence_score=0.95))

    assert result.sql_generation_allowed is True
    assert result.decision_status == DecisionStatus.SQL_ALLOWED
    assert result.next_action == "Proceed to SQL Generation Engine."


def test_blocker_clarification_question_blocks_sql() -> None:
    question = ClarificationQuestion(
        question_id="Q004_Category",
        question="Should the report be for CTC, Orthodox, or all categories?",
        priority=QuestionPriority.BLOCKER,
        related_field="category",
        expected_answer_format="Category or tea type.",
    )

    result = DecisionEngine().decide(
        _analysis(clarification_questions=[question])
    )

    assert result.sql_generation_allowed is False
    assert result.decision_status == DecisionStatus.SQL_BLOCKED
    assert result.next_action == question.question


def test_complete_offline_requirement_reaches_minimum_confidence() -> None:
    analysis = _resolved_offline_analysis(
        "garden ranking for assam ctc est season 2026 upto sale 26"
    )

    result = DecisionEngine().decide(analysis)

    assert result.metadata["confidence_score"] >= 0.85
    assert result.metadata["confidence_score"] <= 0.90


def test_missing_category_remains_below_minimum_confidence() -> None:
    analysis = _resolved_offline_analysis(
        "garden ranking for assam est season 2026 upto sale 26"
    )

    result = DecisionEngine().decide(analysis)

    assert result.metadata["confidence_score"] < 0.85
    assert result.sql_generation_allowed is False


def test_missing_grouping_remains_below_minimum_confidence() -> None:
    known = _complete_known_information().model_copy(update={"output_grain": None})
    analysis = RequirementValidator().validate(_analysis(known_information=known))

    result = DecisionEngine().decide(analysis)

    assert result.metadata["confidence_score"] < 0.85
    assert result.sql_generation_allowed is False


def test_complete_requirement_with_resolvers_can_be_sql_allowed() -> None:
    analysis = _resolved_offline_analysis(
        "garden ranking for assam ctc est season 2026 upto sale 26"
    )

    result = DecisionEngine().decide(analysis)

    assert result.sql_generation_allowed is True
    assert result.decision_status == DecisionStatus.SQL_ALLOWED
