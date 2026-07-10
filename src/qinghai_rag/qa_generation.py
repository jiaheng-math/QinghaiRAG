from __future__ import annotations

import hashlib
import itertools
import logging
from collections import defaultdict

from qinghai_rag.schemas import FactRecord, QARecord

LOGGER = logging.getLogger(__name__)
REFUSAL = "当前数据集中没有足够依据回答。"

RELATION_LABELS = {
    "belongs_to_category": "类别",
    "located_in": "相关地区",
    "protected_by": "保护单位",
    "inherited_by": "代表性传承人",
    "has_level": "项目级别",
    "declared_by": "申报地区或单位",
    "associated_with_ethnic_group": "相关民族",
    "related_to_festival": "相关节庆或活动",
    "mentioned_in_source": "相关来源或概念",
    "related_to_concept": "相关概念",
}


def stable_question_id(question: str) -> str:
    return "q_" + hashlib.sha256(question.encode()).hexdigest()[:12]


def _qa(
    question: str,
    answer: str,
    answer_type: str,
    facts: list[FactRecord],
    entities: list[str],
    difficulty: str,
    unanswerable: bool = False,
) -> QARecord:
    return QARecord(
        question_id=stable_question_id(question),
        question=question,
        answer=answer,
        answer_type=answer_type,
        evidence_fact_ids=[] if unanswerable else sorted({fact.fact_id for fact in facts}),
        evidence_source_ids=[]
        if unanswerable
        else sorted({fact.evidence_source_id for fact in facts}),
        required_entities=entities,
        difficulty=difficulty,
        unanswerable=unanswerable,
        notes="Automatically generated from verified facts; manually review before benchmark release.",
    )


SINGLE_TEMPLATES = {
    "belongs_to_category": ["{s}属于哪一类别？", "根据当前数据，{s}的项目类别是什么？"],
    "located_in": ["{s}与哪个地区相关？", "当前资料将{s}关联到哪里？"],
    "protected_by": ["{s}的保护单位是什么？", "哪个单位负责保护{s}？"],
    "inherited_by": ["{s}的代表性传承人是谁？", "谁传承{s}？"],
    "has_level": ["{s}属于什么级别？", "当前资料记录的{s}项目级别是什么？"],
    "declared_by": ["{s}由哪个地区或单位申报？", "{s}的申报方是谁？"],
    "associated_with_ethnic_group": [
        "{s}与哪个民族相关？",
        "当前资料记录的{s}相关民族是什么？",
    ],
}


def generate_single_fact(facts: list[FactRecord], target: int) -> list[QARecord]:
    eligible = [fact for fact in facts if fact.predicate in SINGLE_TEMPLATES]
    output: dict[str, QARecord] = {}
    if not eligible:
        return []
    for fact, variant in itertools.islice(
        itertools.cycle(itertools.product(eligible, range(2))), target * 4
    ):
        template = SINGLE_TEMPLATES[fact.predicate][variant % len(SINGLE_TEMPLATES[fact.predicate])]
        question = template.format(s=fact.subject)
        item = _qa(
            question, f"{fact.object}。", "single_fact", [fact], [fact.subject, fact.object], "easy"
        )
        output[item.question_id] = item
        if len(output) >= target:
            break
    return list(output.values())


def generate_regional(facts: list[FactRecord], target: int) -> list[QARecord]:
    groups: dict[str, list[FactRecord]] = defaultdict(list)
    for fact in facts:
        if fact.predicate == "located_in":
            groups[fact.object].append(fact)
    output: dict[str, QARecord] = {}
    templates = [
        "{region}地区有哪些已收录的非遗项目？",
        "根据当前事实表，哪些项目与{region}相关？",
        "请列出数据集中关联到{region}的项目。",
        "在现有已核验记录中，{region}关联了哪些项目？",
        "仅依据当前数据，{region}的相关项目有哪些？",
        "汇总当前记录：{region}包含哪些相关项目？",
        "不使用外部知识时，可列出哪些{region}相关项目？",
    ]
    for region, group in groups.items():
        projects = sorted({fact.subject for fact in group})
        answer = "、".join(projects) + "。"
        for template in templates:
            item = _qa(
                template.format(region=region),
                answer,
                "regional_aggregation",
                group,
                [region, *projects],
                "medium",
            )
            output[item.question_id] = item
            if len(output) >= target:
                return list(output.values())
    return list(output.values())


def generate_multi_hop(facts: list[FactRecord], target: int) -> list[QARecord]:
    by_subject: dict[str, list[FactRecord]] = defaultdict(list)
    for fact in facts:
        by_subject[fact.subject].append(fact)
    output: dict[str, QARecord] = {}
    for subject, group in by_subject.items():
        for left, right in itertools.combinations(group, 2):
            if left.predicate == right.predicate:
                continue
            left_label = RELATION_LABELS[left.predicate]
            right_label = RELATION_LABELS[right.predicate]
            question = f"{subject}的{left_label}和{right_label}分别是什么？"
            answer = f"{left_label}：{left.object}；{right_label}：{right.object}。"
            item = _qa(
                question,
                answer,
                "multi_hop",
                [left, right],
                [subject, left.object, right.object],
                "hard",
            )
            output[item.question_id] = item
            if len(output) >= target:
                return list(output.values())
    return list(output.values())


def generate_comparison(facts: list[FactRecord], target: int) -> list[QARecord]:
    by_subject: dict[str, dict[str, FactRecord]] = defaultdict(dict)
    for fact in facts:
        by_subject[fact.subject][fact.predicate] = fact
    output: dict[str, QARecord] = {}
    for left_name, right_name in itertools.combinations(sorted(by_subject), 2):
        common = sorted(set(by_subject[left_name]) & set(by_subject[right_name]))
        if not common:
            continue
        predicate = common[0]
        left, right = by_subject[left_name][predicate], by_subject[right_name][predicate]
        relation_label = RELATION_LABELS[predicate]
        question = f"{left_name}和{right_name}在当前数据中的{relation_label}分别是什么？"
        answer = f"{left_name}：{left.object}；{right_name}：{right.object}。"
        item = _qa(
            question,
            answer,
            "comparison",
            [left, right],
            [left_name, right_name, left.object, right.object],
            "medium",
        )
        output[item.question_id] = item
        if len(output) >= target:
            break
    return list(output.values())


def generate_unanswerable(facts: list[FactRecord], target: int) -> list[QARecord]:
    subjects = sorted({fact.subject for fact in facts}) or ["未收录项目"]
    templates = [
        "{s}上一年度的游客数量是多少？",
        "{s}今天的商业门票价格是多少？",
        "{s}未来五年的营业收入预测是多少？",
        "未收录项目甲的代表性传承人是谁？",
    ]
    output: dict[str, QARecord] = {}
    for subject, template in itertools.islice(
        itertools.cycle(itertools.product(subjects, templates)), target * 4
    ):
        question = template.format(s=subject)
        item = _qa(question, REFUSAL, "unanswerable", [], [subject], "hard", unanswerable=True)
        output[item.question_id] = item
        if len(output) >= target:
            break
    return list(output.values())


def generate_qa(facts: list[FactRecord], minimum: int = 100) -> list[QARecord]:
    verified = [fact for fact in facts if fact.verified and fact.confidence in {"high", "medium"}]
    quotas = {
        "single": max(40, round(minimum * 0.4)),
        "regional": max(20, round(minimum * 0.2)),
        "multi": max(20, round(minimum * 0.2)),
        "comparison": max(10, round(minimum * 0.1)),
        "unanswerable": max(10, minimum - round(minimum * 0.9)),
    }
    records = [
        *generate_single_fact(verified, quotas["single"]),
        *generate_regional(verified, quotas["regional"]),
        *generate_multi_hop(verified, quotas["multi"]),
        *generate_comparison(verified, quotas["comparison"]),
        *generate_unanswerable(verified, quotas["unanswerable"]),
    ]
    unique = {record.question_id: record for record in records}
    if len(unique) < minimum:
        LOGGER.warning(
            "Generated %s/%s QA records; add more verified facts or manually annotate missing types.",
            len(unique),
            minimum,
        )
    return sorted(unique.values(), key=lambda item: item.question_id)
