from qinghai_rag.source_registry import decide_release_policy

CONFIG = {
    "restricted_domains": ["restricted.example"],
    "excluded_domains": ["social.example"],
    "strong_restriction_phrases": ["未经许可不得转载"],
    "government_domains": ["gov.example"],
    "defaults": {
        "unknown_license_status": "unclear",
        "unknown_release_policy": "metadata_and_facts_only",
        "unknown_raw_text_release": False,
    },
}


def test_restricted_domain_overrides_seed_policy():
    decision = decide_release_policy(
        "https://restricted.example/a",
        configured_license="open",
        configured_policy="full_text_allowed",
        config=CONFIG,
    )
    assert decision.release_policy == "metadata_and_facts_only"
    assert decision.raw_text_release is False


def test_restriction_phrase_overrides_government_seed():
    decision = decide_release_policy(
        "https://gov.example/a",
        text="页脚：未经许可不得转载",
        configured_policy="government_public",
        config=CONFIG,
    )
    assert decision.license_status == "restricted"


def test_unknown_is_conservative():
    decision = decide_release_policy("https://unknown.example/a", config=CONFIG)
    assert decision.release_policy == "metadata_and_facts_only"
    assert not decision.raw_text_release
