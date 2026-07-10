from collections import Counter

import pytest

from qinghai_rag.qa_generation import (
    generate_comparison,
    generate_multi_hop,
    generate_regional,
    generate_single_fact,
    generate_unanswerable,
    resolve_qa_minimum,
)
from qinghai_rag.schemas import FactRecord


def _category_fact(fact_id: str, subject: str, category: str) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate="belongs_to_category",
        object=category,
        object_type="CATEGORY",
        evidence_source_id=f"src_{fact_id}",
        evidence_url=f"https://gov.example/{fact_id}",
        extraction_method="table_parse",
        verified=True,
        confidence="high",
    )


def test_comparison_question_uses_chinese_relation_label():
    facts = [
        _category_fact("1", "土族盘绣", "传统技艺"),
        _category_fact("2", "热贡艺术", "传统美术"),
    ]
    [question] = generate_comparison(facts, target=1)
    assert question.question == "土族盘绣和热贡艺术在当前数据中的类别分别是什么？"
    assert "belongs_to_category" not in question.question


def _declared_fact(fact_id: str, subject: str, applicant: str) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate="declared_by",
        object=applicant,
        object_type="ORGANIZATION",
        evidence_source_id=f"src_{fact_id}",
        evidence_url=f"https://gov.example/{fact_id}",
        extraction_method="table_parse",
        verified=True,
        confidence="high",
    )


def test_regional_aggregation_uses_administrative_applicants_not_organizations():
    regional = _declared_fact("1", "热贡艺术", "青海省同仁县")
    organization = _declared_fact("2", "藏医药", "青海省某某药业股份有限公司")

    [question] = generate_regional([regional, organization], target=1)

    assert "青海省同仁县" in question.question
    assert "申报" in question.question
    assert question.evidence_fact_ids == [regional.fact_id]


def test_qa_minimum_defaults_to_configured_release_tier():
    targets = {"tiers": {"v0.1": {"qa": {"min": 300}}}}

    assert resolve_qa_minimum(None, targets) == 300
    assert resolve_qa_minimum(1000, targets) == 1000


def test_qa_minimum_rejects_missing_or_nonpositive_values():
    with pytest.raises(ValueError, match="Missing QA minimum"):
        resolve_qa_minimum(None, {})
    with pytest.raises(ValueError, match="must be positive"):
        resolve_qa_minimum(0, {"tiers": {}})


def test_museum_single_fact_question_uses_material_label():
    fact = FactRecord(
        fact_id="museum_1",
        subject="嵌松石立凤金饰件",
        subject_type="MUSEUM_OBJECT",
        predicate="made_of",
        object="金",
        object_type="MATERIAL",
        evidence_source_id="src_museum_1",
        evidence_url="https://museum.example/1",
        extraction_method="rule",
        verified=True,
        confidence="high",
    )

    [question] = generate_single_fact([fact], target=1)

    assert question.question == "嵌松石立凤金饰件的质地是什么？"
    assert question.answer == "金。"


def test_museum_category_question_does_not_call_object_a_project():
    fact = FactRecord(
        fact_id="museum_category",
        subject="铜质僧帽壶（展品ID：68）",
        subject_type="MUSEUM_OBJECT",
        predicate="belongs_to_category",
        object="金属工艺",
        object_type="CATEGORY",
        evidence_source_id="src_museum_68",
        evidence_url="https://museum.example/68",
        extraction_method="rule",
        verified=True,
        confidence="high",
    )

    [question] = generate_single_fact([fact], target=1)

    assert "项目类别" not in question.question
    assert "文物" in question.question


def test_single_fact_skips_subject_relation_with_multiple_answers():
    facts = [
        _declared_fact("one", "藏族服饰", "青海省玉树藏族自治州"),
        _declared_fact("two", "藏族服饰", "青海省海南藏族自治州"),
    ]

    assert generate_single_fact(facts, target=10) == []


def test_regional_aggregation_deduplicates_reviewed_project_aliases():
    facts = [
        _declared_fact(
            "one", "藏族金属锻造技艺(藏刀锻制技艺)", "青海省玉树藏族自治州"
        ),
        _declared_fact(
            "two", "藏族金属锻制技艺(藏刀锻制技艺)", "青海省玉树藏族自治州"
        ),
    ]

    questions = generate_regional(facts, target=10)

    assert len(questions) == 1
    assert questions[0].answer == "藏族金属锻造技艺(藏刀锻制技艺)。"
    assert questions[0].evidence_fact_ids == ["one", "two"]


def test_comparison_stays_within_one_entity_type():
    project = _category_fact("project", "官磨药香", "传统技艺")
    museum_payload = _category_fact("museum", "《三昧王经》", "书法艺术").model_dump(
        mode="json"
    )
    museum_payload["subject_type"] = "MUSEUM_OBJECT"
    museum = FactRecord.model_validate(museum_payload)

    assert generate_comparison([project, museum], target=1) == []


def test_multi_hop_lists_all_values_for_multi_value_relation():
    declared = _declared_fact("declared", "热贡艺术", "青海省同仁县")
    inheritors = []
    for index, person in enumerate(["西合道", "娘本"], start=1):
        payload = _declared_fact(str(index), "热贡艺术", person).model_dump(mode="json")
        payload.update(
            {
                "predicate": "inherited_by",
                "object_type": "PERSON",
            }
        )
        inheritors.append(FactRecord.model_validate(payload))

    [question] = generate_multi_hop([declared, *inheritors], target=1)

    assert question.answer == "申报地区或单位：青海省同仁县；代表性传承人：娘本、西合道。"
    assert question.evidence_fact_ids == ["1", "2", "declared"]


def _subject_fact(subject: str, subject_type: str) -> FactRecord:
    payload = _category_fact(f"fact_{subject_type}", subject, "测试类别").model_dump(
        mode="json"
    )
    payload["subject_type"] = subject_type
    return FactRecord.model_validate(payload)


def test_unanswerable_museum_questions_are_plausible_for_objects():
    questions = generate_unanswerable([_subject_fact("测试藏品", "MUSEUM_OBJECT")], target=4)

    assert len(questions) == 4
    assert all("门票" not in item.question and "游客" not in item.question for item in questions)
    assert {item.question for item in questions} == {
        "测试藏品的具体出土地点是什么？",
        "测试藏品的入藏日期是哪一天？",
        "测试藏品的文物定级是什么？",
        "测试藏品最近一次修复的日期是什么？",
    }


def test_unanswerable_person_questions_are_plausible_for_people():
    questions = generate_unanswerable([_subject_fact("测试传承人", "PERSON")], target=4)

    assert len(questions) == 4
    assert all("门票" not in item.question and "游客" not in item.question for item in questions)
    assert any("弟子" in item.question for item in questions)
    assert any("代表作品" in item.question for item in questions)


def test_unanswerable_project_questions_request_missing_project_information():
    questions = generate_unanswerable([_subject_fact("测试项目", "ICH_PROJECT")], target=4)

    assert len(questions) == 4
    assert all(
        "门票" not in item.question
        and "展演" not in item.question
        and "课程" not in item.question
        for item in questions
    )
    assert any("保护评估" in item.question for item in questions)
    assert any("专项保护资金" in item.question for item in questions)
    assert any("保护规划文号" in item.question for item in questions)


def test_single_fact_target_is_deterministically_spread_across_subjects():
    facts = [
        _category_fact(f"spread_{index}", f"项目{index:03d}", f"类别{index % 5}")
        for index in range(100)
    ]

    first = generate_single_fact(facts, target=20)
    second = generate_single_fact(list(reversed(facts)), target=20)
    selected_indexes = [int(item.required_entities[0].removeprefix("项目")) for item in first]

    assert [item.question_id for item in first] == [item.question_id for item in second]
    assert max(selected_indexes) - min(selected_indexes) > 50


def test_multi_hop_target_is_spread_across_subjects():
    facts = []
    for index in range(20):
        subject = f"多跳项目{index:02d}"
        facts.extend(
            [
                _category_fact(f"category_{index}", subject, f"类别{index % 3}"),
                _declared_fact(f"declared_{index}", subject, f"青海省测试县{index:02d}"),
                FactRecord(
                    fact_id=f"level_{index}",
                    subject=subject,
                    subject_type="ICH_PROJECT",
                    predicate="has_level",
                    object=f"级别{index % 2}",
                    object_type="CONCEPT",
                    evidence_source_id=f"src_level_{index}",
                    evidence_url=f"https://gov.example/level_{index}",
                    extraction_method="table_parse",
                    verified=True,
                    confidence="high",
                ),
            ]
        )

    questions = generate_multi_hop(facts, target=20)

    assert len({item.required_entities[0] for item in questions}) >= 10


def test_comparison_target_spreads_subjects_and_relation_types():
    facts = []
    for index in range(20):
        subject = f"藏品{index:02d}"
        for predicate, value, object_type in [
            ("belongs_to_category", f"类别{index % 3}", "CATEGORY"),
            ("created_in_period", f"年代{index % 4}", "HISTORICAL_PERIOD"),
            ("made_of", f"材质{index % 5}", "MATERIAL"),
            ("held_by", "同一博物馆", "ORGANIZATION"),
        ]:
            facts.append(
                FactRecord(
                    fact_id=f"{predicate}_{index}",
                    subject=subject,
                    subject_type="MUSEUM_OBJECT",
                    predicate=predicate,
                    object=value,
                    object_type=object_type,
                    evidence_source_id=f"src_{index}",
                    evidence_url=f"https://museum.example/{index}",
                    extraction_method="rule",
                    verified=True,
                    confidence="high",
                )
            )

    questions = generate_comparison(facts, target=20)
    subject_counts = Counter(
        subject for item in questions for subject in item.required_entities[:2]
    )
    used_labels = {
        label
        for label in ["类别", "年代", "质地"]
        if any(f"中的{label}" in item.question for item in questions)
    }

    assert len(questions) == 20
    assert max(subject_counts.values()) < 10
    assert len(used_labels) >= 2
    assert all("馆藏机构" not in item.question for item in questions)


@pytest.mark.parametrize("predicate", ["related_to_concept", "mentioned_in_source"])
def test_metadata_relations_do_not_enter_multi_hop_or_comparison_qa(predicate):
    facts = [
        _category_fact("category_one", "项目甲", "传统技艺"),
        _category_fact("category_two", "项目乙", "传统美术"),
    ]
    for index, subject in enumerate(["项目甲", "项目乙"], start=1):
        facts.append(
            FactRecord(
                fact_id=f"metadata_{index}",
                subject=subject,
                subject_type="ICH_PROJECT",
                predicate=predicate,
                object="第三批县级非遗代表性项目拟入选名单",
                object_type="CONCEPT",
                evidence_source_id=f"src_metadata_{index}",
                evidence_url=f"https://gov.example/metadata_{index}",
                extraction_method="manual_review",
                verified=True,
                confidence="high",
            )
        )

    multi_hop = generate_multi_hop(facts, target=10)
    comparisons = generate_comparison(facts, target=10)

    assert multi_hop == []
    assert all("相关概念" not in item.question for item in comparisons)
    assert all("相关来源" not in item.question for item in comparisons)
