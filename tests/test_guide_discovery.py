from qinghai_rag.guide_discovery import (
    deduplicate_guide_candidates,
    discover_guide_tourism,
    guide_section_page_url,
    parse_guide_tourism_page,
)


def _page(*links: tuple[str, str, str], total: int = 2, pages: int = 1) -> str:
    items = "".join(
        f'''<a href="{href}" title="标题：{title}&#xD;&#xA;点击数：1&#xD;&#xA;发表时间：{published}">{title}</a>'''
        for href, title, published in links
    )
    return f"""<div>{items}</div><div class="page"><span class="total">共{total}条信息/共{pages}页</span></div>"""


def test_guide_page_builds_conservative_county_candidates():
    html = _page(
        (
            "/gdly/jqjd/content_101",
            "黄河湿地公园非遗旅游线路",
            "2026-06-16",
        ),
        total=1,
    )

    [candidate], metadata = parse_guide_tourism_page(
        html, section="jqjd", discovered_at="2026-07-10"
    )

    assert metadata == {"reported_total": 1, "total_pages": 1}
    assert candidate.source_id == "src_guide_content_101"
    assert candidate.url == "https://www.guide.gov.cn/gdly/jqjd/content_101"
    assert candidate.source_type.value == "municipal_or_county_government"
    assert candidate.region == ["青海省", "海南藏族自治州", "贵德县"]
    assert candidate.release_policy.value == "metadata_and_facts_only"
    assert candidate.raw_text_release is False
    assert "景区与文化地点" in candidate.topic
    assert "生态旅游" in candidate.topic
    assert "非遗" in candidate.topic


def test_guide_discovery_follows_section_pagination_and_deduplicates_titles():
    pages = {
        guide_section_page_url("wlzx", 1): _page(
            ("/gdly/wlzx/content_1", "非遗活动", "2026-01-01"),
            total=2,
            pages=2,
        ),
        guide_section_page_url("wlzx", 2): _page(
            ("/gdly/wlzx/content_2", "非遗活动", "2026-01-02"),
            total=2,
            pages=2,
        ),
    }

    records, metadata = discover_guide_tourism(
        sections=["wlzx"],
        interval_seconds=0,
        fetch_html=pages.__getitem__,
    )

    assert len(records) == 1
    assert records[0].source_id == "src_guide_content_2"
    assert metadata["reported_total"] == 2
    assert metadata["total_pages"] == 2
    assert metadata["fetched_pages"] == 2
    assert metadata["deduplicated_titles"] == 1


def test_guide_candidate_deduplication_keeps_distinct_titles():
    html = _page(
        ("/gdly/tsms/content_1", "地方美食甲", "2025-01-01"),
        ("/gdly/tsms/content_2", "地方美食乙", "2025-01-02"),
    )
    records, _ = parse_guide_tourism_page(html, section="tsms")

    assert len(deduplicate_guide_candidates(records)) == 2
