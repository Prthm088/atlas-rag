from atlas.evaluation import parse_sse, score_answer


def test_grounded_answer_score_requires_terms_and_citation() -> None:
    case = {
        "id": "retrieval",
        "expected_terms": ["pgvector", "full-text", "fusion"],
        "forbidden_terms": ["moon"],
        "expect_refusal": False,
    }
    score = score_answer(case, "It uses pgvector, full-text search, and fusion [C1].", 1)
    assert score.passed
    assert score.term_recall == 1.0


def test_refusal_score_rejects_hallucinated_forbidden_terms() -> None:
    case = {
        "id": "unknown",
        "expected_terms": [],
        "forbidden_terms": ["pizza"],
        "expect_refusal": True,
    }
    good = score_answer(case, "The documents do not contain enough evidence to answer that.", 0)
    bad = score_answer(case, "The documents do not contain enough evidence, but probably pizza.", 0)
    assert good.passed
    assert not bad.passed


def test_sse_parser_handles_multiple_events() -> None:
    events = parse_sse('event: token\ndata: {"text":"A"}\n\nevent: done\ndata: {"content":"A"}\n\n')
    assert events == [("token", {"text": "A"}), ("done", {"content": "A"})]
