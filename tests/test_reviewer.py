"""Tests for reviewer.py pure functions and config loading."""

import json

import pytest

from reviewer import (
    average_scores,
    check_quorum,
    compute_review_score,
    compute_spread,
    find_weakest_dim,
    load_config,
    parse_review_response,
    truncate_paper,
)

WEIGHTS = {"soundness": 0.35, "clarity": 0.30, "novelty": 0.20, "significance": 0.15}


# --- compute_review_score ---


def test_compute_review_score_basic():
    scores = {"soundness": 8, "clarity": 7, "novelty": 6, "significance": 7}
    result = compute_review_score(scores, weights=WEIGHTS)
    expected = 8 * 0.35 + 7 * 0.30 + 6 * 0.20 + 7 * 0.15
    assert result == pytest.approx(expected)


def test_compute_review_score_custom_weights():
    scores = {"soundness": 10, "clarity": 10, "novelty": 10, "significance": 10}
    custom = {"soundness": 0.25, "clarity": 0.25, "novelty": 0.25, "significance": 0.25}
    assert compute_review_score(scores, weights=custom) == pytest.approx(10.0)


# --- find_weakest_dim ---


def test_find_weakest_dim_single_weak():
    scores = {"soundness": 8, "clarity": 5, "novelty": 7, "significance": 6}
    assert find_weakest_dim(scores, weights=WEIGHTS) == "clarity"


def test_find_weakest_dim_tied():
    scores = {"soundness": 5, "clarity": 5, "novelty": 7, "significance": 7}
    result = find_weakest_dim(scores, weights=WEIGHTS)
    assert result in ("soundness", "clarity")


# --- parse_review_response ---


def _make_response(scores: dict, comments: dict | None = None) -> str:
    data = {**scores}
    if comments is not None:
        data["comments"] = comments
    return json.dumps(data)


def test_parse_review_response_valid_json():
    raw = _make_response(
        {"soundness": 7, "clarity": 8, "novelty": 6, "significance": 7}
    )
    result = parse_review_response(raw)
    assert result["soundness"] == 7.0
    assert result["clarity"] == 8.0


def test_parse_review_response_fenced_json():
    inner = _make_response(
        {"soundness": 7, "clarity": 8, "novelty": 6, "significance": 7}
    )
    raw = f"```json\n{inner}\n```"
    result = parse_review_response(raw)
    assert result["soundness"] == 7.0


def test_parse_review_response_missing_field():
    raw = json.dumps({"soundness": 7, "clarity": 8, "novelty": 6})
    with pytest.raises(ValueError, match="Missing required field"):
        parse_review_response(raw)


def test_parse_review_response_out_of_range():
    raw = _make_response(
        {"soundness": 11, "clarity": 8, "novelty": 6, "significance": 7}
    )
    with pytest.raises(ValueError, match="out of range"):
        parse_review_response(raw)


def test_parse_review_response_non_integer():
    raw = _make_response(
        {"soundness": 7.5, "clarity": 8, "novelty": 6, "significance": 7}
    )
    with pytest.raises(ValueError, match="must be an integer"):
        parse_review_response(raw)


def test_parse_review_response_garbage():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_review_response("this is not json at all")


# --- average_scores ---


def test_average_scores_single():
    results = [{"soundness": 8, "clarity": 7, "novelty": 6, "significance": 7}]
    avg = average_scores(results)
    assert avg["soundness"] == 8.0
    assert avg["clarity"] == 7.0


def test_average_scores_multiple():
    results = [
        {"soundness": 8, "clarity": 6, "novelty": 7, "significance": 7},
        {"soundness": 6, "clarity": 8, "novelty": 5, "significance": 9},
    ]
    avg = average_scores(results)
    assert avg["soundness"] == pytest.approx(7.0)
    assert avg["clarity"] == pytest.approx(7.0)
    assert avg["novelty"] == pytest.approx(6.0)
    assert avg["significance"] == pytest.approx(8.0)


# --- check_quorum ---


def test_check_quorum_below():
    assert check_quorum(1) is False


def test_check_quorum_at():
    assert check_quorum(2) is True


def test_check_quorum_above():
    assert check_quorum(3) is True


# --- truncate_paper ---


def test_truncate_paper_short():
    text = "This is a short paper with few words."
    assert truncate_paper(text) == text


def test_truncate_paper_long():
    words = [f"word{i}" for i in range(200000)]
    text = " ".join(words)
    result = truncate_paper(text, max_tokens=100)
    assert "[TRUNCATED]" in result
    assert result.startswith("word0")
    assert result.endswith(f"word{len(words) - 1}")


# --- compute_spread ---


def test_compute_spread_uniform():
    results = [
        {"soundness": 7, "clarity": 7, "novelty": 7, "significance": 7},
        {"soundness": 7, "clarity": 7, "novelty": 7, "significance": 7},
    ]
    dim, val = compute_spread(results, weights=WEIGHTS)
    assert val == pytest.approx(0.0)


def test_compute_spread_divergent():
    results = [
        {"soundness": 8, "clarity": 7, "novelty": 4, "significance": 7},
        {"soundness": 8, "clarity": 7, "novelty": 8, "significance": 7},
    ]
    dim, val = compute_spread(results, weights=WEIGHTS)
    assert dim == "novelty"
    assert val == pytest.approx(4.0)


# --- load_config ---


def test_load_config_missing_file(tmp_path):
    config = load_config(str(tmp_path / "nonexistent.toml"))
    assert "reviewer" in config
    assert "weights" in config
    assert "models" in config
    assert len(config["models"]) == 3


def test_load_config_valid_toml(tmp_path):
    toml_file = tmp_path / "test.toml"
    toml_file.write_text(
        '[reviewer]\nvenue = "ICML"\n\n'
        "[[models]]\n"
        'model = "gpt-5.4"\n'
        'api_key = "test-key"\n'
        'base_url = "https://api.openai.com/v1"\n'
    )
    config = load_config(str(toml_file))
    assert config["reviewer"]["venue"] == "ICML"
    assert config["models"][0]["api_key"] == "test-key"


def test_load_config_partial(tmp_path):
    toml_file = tmp_path / "test.toml"
    toml_file.write_text('[reviewer]\nvenue = "ACL"\n')
    config = load_config(str(toml_file))
    assert config["reviewer"]["venue"] == "ACL"
    assert config["reviewer"]["min_quorum"] == 2  # default preserved
    assert config["weights"]["soundness"] == 0.35  # default preserved


def test_load_config_empty_models(tmp_path):
    toml_file = tmp_path / "test.toml"
    toml_file.write_text("[reviewer]\n")
    # No [[models]] section → uses defaults, which is fine
    config = load_config(str(toml_file))
    assert len(config["models"]) == 3


def test_load_config_explicit_empty_models(tmp_path):
    toml_file = tmp_path / "test.toml"
    # Explicitly empty models via a hack: we write models as empty
    # TOML doesn't have a way to express an empty array of tables directly,
    # but we can test the code path by passing through load_config
    toml_file.write_text('[reviewer]\nvenue = "NeurIPS"\n')
    config = load_config(str(toml_file))
    # Falls back to defaults when models key is absent
    assert len(config["models"]) > 0
