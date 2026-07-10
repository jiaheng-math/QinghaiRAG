from qinghai_rag.fact_extraction import extract_table_facts
from qinghai_rag.schemas import SourceRecord


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
