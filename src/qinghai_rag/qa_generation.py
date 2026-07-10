from __future__ import annotations

import hashlib
import itertools
import logging
import re
from collections import defaultdict

from qinghai_rag.normalize import normalize_entity_name
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
    "held_by": "馆藏机构",
    "created_in_period": "年代",
    "made_of": "质地",
}


def resolve_qa_minimum(
    requested: int | None,
    scale_targets: dict,
    tier: str = "v0.1",
) -> int:
    if requested is not None:
        if requested <= 0:
            raise ValueError("QA minimum must be positive")
        return requested
    try:
        minimum = int(scale_targets["tiers"][tier]["qa"]["min"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Missing QA minimum for release tier {tier}") from exc
    if minimum <= 0:
        raise ValueError("Configured QA minimum must be positive")
    return minimum


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
    "held_by": ["{s}由哪个机构收藏？", "当前资料记录的{s}馆藏机构是什么？"],
    "created_in_period": ["{s}属于哪个年代？", "当前资料记录的{s}年代是什么？"],
    "made_of": ["{s}的质地是什么？", "当前资料记录的{s}由什么材质制成？"],
}

MUSEUM_SINGLE_TEMPLATES = {
    "belongs_to_category": ["{s}属于哪类文物？", "当前资料记录的{s}文物类别是什么？"],
}


def _canonical_values(facts: list[FactRecord]) -> list[str]:
    return sorted({normalize_entity_name(fact.object) for fact in facts})


def _template_variant(key: str, size: int) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % size


def generate_single_fact(facts: list[FactRecord], target: int) -> list[QARecord]:
    grouped: dict[tuple[str, str, str], list[FactRecord]] = defaultdict(list)
    for fact in facts:
        if fact.predicate in SINGLE_TEMPLATES:
            grouped[(normalize_entity_name(fact.subject), fact.subject_type, fact.predicate)].append(
                fact
            )

    output = []
    for (subject, subject_type, predicate), group in sorted(grouped.items()):
        objects = _canonical_values(group)
        if len(objects) != 1:
            continue
        templates = (
            MUSEUM_SINGLE_TEMPLATES.get(predicate, SINGLE_TEMPLATES[predicate])
            if subject_type == "MUSEUM_OBJECT"
            else SINGLE_TEMPLATES[predicate]
        )
        variant = _template_variant(f"{subject_type}\0{subject}\0{predicate}", len(templates))
        question = templates[variant].format(s=subject)
        item = _qa(
            question,
            f"{objects[0]}。",
            "single_fact",
            group,
            [subject, objects[0]],
            "easy",
        )
        output.append(item)
    return sorted(output, key=lambda item: item.question_id)[:target]


def generate_regional(facts: list[FactRecord], target: int) -> list[QARecord]:
    groups: dict[tuple[str, str], list[FactRecord]] = defaultdict(list)
    for fact in facts:
        if fact.predicate == "located_in":
            groups[(fact.predicate, fact.object)].append(fact)
        elif fact.predicate == "declared_by" and re.search(
            r"(?:省|市|县|区|州|自治县|自治州)$", fact.object
        ):
            groups[(fact.predicate, fact.object)].append(fact)
    output: dict[str, QARecord] = {}
    located_templates = [
        "{region}地区有哪些已收录的非遗项目？",
        "根据当前事实表，哪些项目与{region}相关？",
        "请列出数据集中关联到{region}的项目。",
        "在现有已核验记录中，{region}关联了哪些项目？",
        "仅依据当前数据，{region}的相关项目有哪些？",
        "汇总当前记录：{region}包含哪些相关项目？",
        "不使用外部知识时，可列出哪些{region}相关项目？",
    ]
    declared_templates = [
        "{region}申报了哪些已收录的非遗项目？",
        "根据当前事实表，由{region}申报的项目有哪些？",
        "请列出数据集中申报方为{region}的项目。",
        "在现有已核验记录中，哪些项目由{region}申报？",
        "仅依据当前数据，可列出哪些{region}申报的项目？",
        "汇总当前记录：{region}对应的申报项目有哪些？",
        "不使用外部知识时，能确认哪些项目由{region}申报？",
    ]
    for (predicate, region), group in sorted(groups.items()):
        projects = sorted({normalize_entity_name(fact.subject) for fact in group})
        answer = "、".join(projects) + "。"
        templates = located_templates if predicate == "located_in" else declared_templates
        variant = _template_variant(f"{predicate}\0{region}", len(templates))
        item = _qa(
            templates[variant].format(region=region),
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
    by_subject: dict[tuple[str, str], dict[str, list[FactRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for fact in facts:
        if fact.predicate not in SINGLE_TEMPLATES:
            continue
        by_subject[(normalize_entity_name(fact.subject), fact.subject_type)][fact.predicate].append(
            fact
        )
    output: dict[str, QARecord] = {}
    for (subject, _subject_type), relations in sorted(by_subject.items()):
        for left_predicate, right_predicate in itertools.combinations(sorted(relations), 2):
            left_group = relations[left_predicate]
            right_group = relations[right_predicate]
            left_values = _canonical_values(left_group)
            right_values = _canonical_values(right_group)
            left_label = RELATION_LABELS[left_predicate]
            right_label = RELATION_LABELS[right_predicate]
            question = f"{subject}的{left_label}和{right_label}分别是什么？"
            answer = (
                f"{left_label}：{'、'.join(left_values)}；"
                f"{right_label}：{'、'.join(right_values)}。"
            )
            item = _qa(
                question,
                answer,
                "multi_hop",
                [*left_group, *right_group],
                [subject, *left_values, *right_values],
                "hard",
            )
            output[item.question_id] = item
    return sorted(output.values(), key=lambda item: item.question_id)[:target]


def generate_comparison(facts: list[FactRecord], target: int) -> list[QARecord]:
    by_subject: dict[tuple[str, str], dict[str, list[FactRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for fact in facts:
        if fact.predicate not in SINGLE_TEMPLATES:
            continue
        by_subject[(normalize_entity_name(fact.subject), fact.subject_type)][fact.predicate].append(
            fact
        )
    keys_by_type: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in by_subject:
        keys_by_type[key[1]].append(key)
    pairs = []
    for subject_type, keys in keys_by_type.items():
        ordered = sorted(
            keys,
            key=lambda key: hashlib.sha256(
                f"{subject_type}\0{key[0]}".encode()
            ).hexdigest(),
        )
        pairs.extend(itertools.combinations(ordered, 2))
    pairs.sort(
        key=lambda pair: hashlib.sha256(
            f"{pair[0][1]}\0{pair[0][0]}\0{pair[1][0]}".encode()
        ).hexdigest()
    )

    output: dict[str, QARecord] = {}
    for left_key, right_key in pairs:
        left_name, left_type = left_key
        right_name, _right_type = right_key
        common = sorted(set(by_subject[left_key]) & set(by_subject[right_key]))
        if not common:
            continue
        eligible = []
        for predicate in common:
            left_group = by_subject[left_key][predicate]
            right_group = by_subject[right_key][predicate]
            left_values = _canonical_values(left_group)
            right_values = _canonical_values(right_group)
            if (
                len(left_values) == 1
                and len(right_values) == 1
                and left_values != right_values
            ):
                eligible.append(
                    (predicate, left_group, right_group, left_values, right_values)
                )
        if not eligible:
            continue
        predicate, left_group, right_group, left_values, right_values = eligible[
            _template_variant(f"{left_type}\0{left_name}\0{right_name}", len(eligible))
        ]
        relation_label = RELATION_LABELS[predicate]
        question = f"{left_name}和{right_name}在当前数据中的{relation_label}分别是什么？"
        answer = f"{left_name}：{left_values[0]}；{right_name}：{right_values[0]}。"
        item = _qa(
            question,
            answer,
            "comparison",
            [*left_group, *right_group],
            [left_name, right_name, left_values[0], right_values[0]],
            "medium",
        )
        output[item.question_id] = item
        if len(output) >= target:
            break
    return list(output.values())


def generate_unanswerable(facts: list[FactRecord], target: int) -> list[QARecord]:
    templates_by_type = {
        "ICH_PROJECT": [
            "{s}最近一次保护评估的具体得分是多少？",
            "{s}上一年度获得的专项保护资金是多少？",
            "{s}最近一次保护评估的具体日期是什么？",
            "{s}当前执行的保护规划文号是什么？",
        ],
        "MUSEUM_OBJECT": [
            "{s}的具体出土地点是什么？",
            "{s}的入藏日期是哪一天？",
            "{s}的文物定级是什么？",
            "{s}最近一次修复的日期是什么？",
        ],
        "PERSON": [
            "{s}获得过哪些国家级奖项？",
            "{s}目前有多少名正式弟子？",
            "{s}最近一次公开传习活动是什么时候？",
            "{s}的完整代表作品目录是什么？",
        ],
    }
    generic_templates = [
        "{s}最新一次官方更新的具体日期是什么？",
        "{s}对应的最新年度统计数据是多少？",
        "{s}最近一次正式审查的结论是什么？",
        "{s}的完整档案编号是什么？",
    ]
    subjects = sorted(
        {(normalize_entity_name(fact.subject), fact.subject_type) for fact in facts}
    ) or [("未收录项目甲", "ICH_PROJECT")]
    candidates: list[tuple[str, str]] = []
    for subject, subject_type in subjects:
        templates = templates_by_type.get(subject_type, generic_templates)
        candidates.extend((template.format(s=subject), subject) for template in templates)

    output: dict[str, QARecord] = {}
    for question, subject in sorted(
        candidates, key=lambda value: hashlib.sha256(value[0].encode()).hexdigest()
    ):
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
    pools = {
        "single": generate_single_fact(verified, minimum),
        "regional": generate_regional(verified, minimum),
        "multi": generate_multi_hop(verified, minimum),
        "comparison": generate_comparison(verified, minimum),
        "unanswerable": generate_unanswerable(verified, quotas["unanswerable"]),
    }
    unique: dict[str, QARecord] = {}
    for kind in ("single", "regional", "multi", "comparison", "unanswerable"):
        for record in pools[kind][: quotas[kind]]:
            unique[record.question_id] = record
    if len(unique) < minimum:
        for kind in ("single", "multi", "comparison", "regional"):
            for record in pools[kind]:
                unique[record.question_id] = record
                if len(unique) >= minimum:
                    break
            if len(unique) >= minimum:
                break
    if len(unique) < minimum:
        LOGGER.warning(
            "Generated %s/%s QA records; add more verified facts or manually annotate missing types.",
            len(unique),
            minimum,
        )
    return sorted(unique.values(), key=lambda item: item.question_id)
