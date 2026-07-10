from qinghai_rag.coverage import compute_source_coverage, render_coverage_markdown
from qinghai_rag.schemas import SourceRecord


def _source(source_id, source_type, *, title="", topic=None, region=None, status="parsed"):
    return SourceRecord(
        source_id=source_id,
        title=title or source_id,
        publisher="官方机构",
        source_type=source_type,
        url=f"https://example.gov.cn/{source_id}",
        domain="example.gov.cn",
        topic=topic or [],
        region=region or [],
        retrieved_at="2026-07-10",
        release_policy="metadata_and_facts_only",
        crawl_status=status,
    )


def test_coverage_audit_resolves_county_aliases_and_reports_gaps():
    targets = {
        "source_levels": {
            "national": {
                "label": "国家级",
                "source_types": ["national_official_database"],
                "min_sources": 1,
            },
            "local": {
                "label": "市县级",
                "source_types": ["municipal_or_county_government"],
                "min_sources": 1,
            },
        },
        "topics": {
            "非遗": {"aliases": ["非遗"], "min_sources": 1},
            "生态旅游": {"aliases": ["生态旅游", "青海湖"], "min_sources": 1},
        },
        "regions": {
            "海东市": {"aliases": ["海东市", "互助土族自治县"], "min_sources": 1},
            "海西蒙古族藏族自治州": {
                "aliases": ["海西蒙古族藏族自治州"],
                "min_sources": 1,
            },
        },
    }
    sources = [
        _source(
            "s1",
            "national_official_database",
            title="土族盘绣非遗项目",
            topic=["非遗"],
            region=["青海省互助土族自治县"],
        ),
        _source(
            "s2",
            "provincial_culture_tourism_department",
            title="青海湖生态旅游",
            topic=["文旅动态", "生态旅游"],
            region=["青海省"],
        ),
        _source(
            "s3",
            "provincial_culture_tourism_department",
            title="旧链接",
            topic=["文旅动态"],
            region=["青海省"],
            status="failed",
        ),
    ]

    report = compute_source_coverage(sources, targets)

    assert report["assessment"]["topics"]["生态旅游"]["count"] == 1
    assert report["assessment"]["regions"]["海东市"]["count"] == 1
    assert report["region_topic_matrix"]["海东市"]["非遗"] == 1
    assert report["coverage_sources"] == 2
    assert report["crawl_status_distribution"] == {"failed": 1, "parsed": 2}
    assert {item["value"] for item in report["gaps"]} == {
        "local",
        "海西蒙古族藏族自治州",
    }
    assert "Region × topic matrix" in render_coverage_markdown(report)


def test_coverage_does_not_infer_topic_from_site_brand_in_title():
    targets = {
        "topics": {
            "博物馆与文化场馆": {
                "aliases": ["博物馆", "文化馆"],
                "min_sources": 1,
            }
        }
    }
    source = _source(
        "s1",
        "national_official_database",
        title="热贡艺术 - 中国非物质文化遗产数字博物馆",
        topic=["非遗", "传统美术"],
    )

    report = compute_source_coverage([source], targets)

    assert report["assessment"]["topics"]["博物馆与文化场馆"]["count"] == 0
