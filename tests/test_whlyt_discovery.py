from qinghai_rag.whlyt_discovery import (
    deduplicate_whlyt_candidates,
    inspect_whlyt_article,
    parse_whlyt_search_page,
    whlyt_user_agent,
)


def test_whlyt_search_page_builds_restricted_metadata_candidates():
    html = """
    <div class="search-info">搜索到相关结果约: <div class="total">162</div></div>
    <div class="search-result">
      <div class="app-article-list">
        <a class="app-article-item" cid="57" contentId="23988"
           href="https://whlyt.qinghai.gov.cn/content/23986">
          <div class="app-article-title">“非遗贺新春”展演活动启动</div>
          <div class="app-article-date">2025-01-16 11:08:19</div>
        </a>
        <a class="app-article-item" cid="57" contentId="bad" href="/s">
          <div class="app-article-title">无效链接</div>
          <div class="app-article-date">2025-01-16 11:08:19</div>
        </a>
      </div>
    </div>
    <div class="app-pagination">
      <a href="/search?keyword=x&page=11" class="last">尾页</a>
    </div>
    """
    [candidate], metadata = parse_whlyt_search_page(html, discovered_at="2026-07-10")
    assert metadata == {"reported_total": 162, "total_pages": 11}
    assert candidate.source_id == "src_whlyt_content_23986"
    assert candidate.url == "http://whlyt.qinghai.gov.cn/content/23986"
    assert candidate.catalog_metadata["search_content_id"] == "23988"
    assert candidate.catalog_metadata["published_at"] == "2025-01-16 11:08:19"
    assert candidate.license_status.value == "government_public"
    assert candidate.release_policy.value == "government_public"
    assert candidate.raw_text_release is True


def test_whlyt_article_requires_site_ownership_attribution_and_no_page_restriction():
    html = """
    <meta name="ContentSource" content="青海省文化和旅游厅">
    <div class="app-content-body"><p>青海非遗活动正文。</p></div>
    """
    inspection = inspect_whlyt_article(html)
    assert inspection["eligible_full_text"] is True
    assert inspection["reasons"] == []

    third_party = inspect_whlyt_article(
        html.replace("青海省文化和旅游厅", "青海日报")
    )
    assert third_party["eligible_full_text"] is False
    assert "third_party_or_missing_content_source" in third_party["reasons"]

    restricted = inspect_whlyt_article(
        html.replace("青海非遗活动正文。", "青海非遗活动正文。未经许可不得转载。")
    )
    assert restricted["eligible_full_text"] is False
    assert "page_specific_restriction" in restricted["reasons"]


def test_whlyt_user_agent_transparently_identifies_project_and_contact():
    value = whlyt_user_agent("maintainer@example.org")
    assert value == (
        "QinghaiRAG/0.1 (+maintainer@example.org; provenance-first research crawler)"
    )


def test_whlyt_duplicate_titles_prefer_primary_section_then_newer_date():
    html = """
    <div class="search-info"><div class="total">3</div></div>
    <a class="app-article-item" href="/dffc/100.html">
      <div class="app-article-title">同一非遗活动</div>
      <div class="app-article-date">2026-02-03 10:00:00</div>
    </a>
    <a class="app-article-item" href="/qhwl/101.html">
      <div class="app-article-title">同一非遗活动</div>
      <div class="app-article-date">2026-02-01 10:00:00</div>
    </a>
    <a class="app-article-item" href="/qhwl/102.html">
      <div class="app-article-title">同一非遗活动</div>
      <div class="app-article-date">2026-02-02 10:00:00</div>
    </a>
    """
    records, _ = parse_whlyt_search_page(html, discovered_at="2026-07-10")
    [selected] = deduplicate_whlyt_candidates(records)
    assert selected.url == "http://whlyt.qinghai.gov.cn/qhwl/102.html"
