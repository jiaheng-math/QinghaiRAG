from qinghai_rag.fact_extraction import extract_table_facts, merge_extracted_facts
from qinghai_rag.schemas import FactRecord, SourceRecord


def test_extracts_supported_table_relations():
    source = SourceRecord(
        source_id="src_test",
        title="表格",
        publisher="机构",
        source_type="provincial_government",
        url="https://gov.example/table",
        domain="gov.example",
        retrieved_at="2026-07-10",
        license_status="government_public",
        release_policy="government_public",
        raw_text_release=True,
        crawl_status="parsed",
    )
    html = """
    <table>
      <tr><th>项目名称</th><th>类别</th><th>所属地区</th><th>保护单位</th></tr>
      <tr><td>测试项目</td><td>传统技艺</td><td>海东</td><td>测试单位</td></tr>
    </table>
    """
    facts = extract_table_facts(html, source)
    assert {fact.predicate for fact in facts} == {
        "belongs_to_category",
        "located_in",
        "protected_by",
    }
    assert next(fact.object for fact in facts if fact.predicate == "located_in") == "海东市"
    assert all(fact.evidence_source_id == "src_test" for fact in facts)


def test_strips_repeated_column_labels_from_responsive_tables():
    source = SourceRecord(
        source_id="src_test",
        title="表格",
        publisher="机构",
        source_type="national_official_database",
        url="https://gov.example/table",
        domain="gov.example",
        retrieved_at="2026-07-10",
        license_status="unclear",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="parsed",
    )
    html = """
    <table>
      <tr><th>类别</th><th>项目名称</th><th>申报地区或单位</th></tr>
      <tr>
        <td>类别 传统美术</td>
        <td>项目名称 热贡艺术</td>
        <td>申报地区或单位 青海省同仁县</td>
      </tr>
      <tr>
        <td>类别 传统美术</td>
        <td>项目名称 区外相关项目</td>
        <td>申报地区或单位 西藏自治区昌都市</td>
      </tr>
    </table>
    """
    facts = extract_table_facts(html, source)
    assert {(fact.subject, fact.predicate, fact.object) for fact in facts} == {
        ("热贡艺术", "belongs_to_category", "传统美术"),
        ("热贡艺术", "declared_by", "青海省同仁县"),
    }


def test_ihchina_page_only_extracts_the_project_named_by_the_page_title():
    source = SourceRecord(
        source_id="src_ihchina_12934",
        title="锅庄舞（玉树卓舞） - 中国非物质文化遗产网·中国非物质文化遗产数字博物馆",
        publisher="中国非物质文化遗产网",
        source_type="national_official_database",
        url="https://www.ihchina.cn/project_details/12934.html",
        domain="ihchina.cn",
        region=["青海省", "青海省玉树市"],
        retrieved_at="2026-07-10",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="parsed",
    )
    html = """
    <table>
      <tr><th>项目名称</th><th>类别</th><th>申报地区或单位</th></tr>
      <tr><td>锅庄舞(囊谦卓干玛)</td><td>传统舞蹈</td><td>青海省囊谦县</td></tr>
      <tr><td>锅庄舞(玉树卓舞)</td><td>传统舞蹈</td><td>青海省称多县</td></tr>
      <tr><td>锅庄舞(玉树卓舞)</td><td>传统舞蹈</td><td>青海省玉树市</td></tr>
      <tr><td>锅庄舞(称多白龙卓舞)</td><td>传统舞蹈</td><td>青海省称多县</td></tr>
    </table>
    """
    facts = extract_table_facts(html, source)
    assert {fact.subject for fact in facts} == {"锅庄舞(玉树卓舞)"}
    assert {
        fact.object for fact in facts if fact.predicate == "declared_by"
    } == {"青海省玉树市"}


def _fact(fact_id: str, *, verified: bool = False) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject="项目",
        subject_type="ICH_PROJECT",
        predicate="belongs_to_category",
        object="传统美术",
        object_type="CATEGORY",
        evidence_source_id="src_1",
        evidence_url="https://gov.example/1",
        extraction_method="table_parse",
        verified=verified,
        manual_checked=verified,
        confidence="medium",
    )


def test_merge_preserves_reviewed_facts_and_prunes_stale_unreviewed_facts():
    reviewed = _fact("fact_reviewed", verified=True)
    refreshed_copy = _fact("fact_reviewed")
    current = _fact("fact_current")
    stale = _fact("fact_stale")

    merged = merge_extracted_facts([reviewed, stale], [refreshed_copy, current])

    assert {fact.fact_id for fact in merged} == {"fact_reviewed", "fact_current"}
    assert next(fact for fact in merged if fact.fact_id == "fact_reviewed").verified is True
