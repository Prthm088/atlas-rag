import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(slots=True)
class CaseScore:
    case_id: str
    passed: bool
    term_recall: float
    citation_present: bool
    refusal_detected: bool
    forbidden_term_hits: list[str]


def score_answer(case: dict[str, Any], answer: str, citation_count: int) -> CaseScore:
    normalized = answer.casefold()
    expected = [str(term).casefold() for term in case.get("expected_terms", [])]
    forbidden = [str(term) for term in case.get("forbidden_terms", []) if str(term).casefold() in normalized]
    matched = sum(term in normalized for term in expected)
    recall = matched / len(expected) if expected else 1.0
    refusal_markers = (
        "not enough evidence",
        "don’t contain enough evidence",
        "do not contain enough evidence",
        "couldn’t find enough evidence",
        "cannot find enough evidence",
    )
    refusal = any(marker in normalized for marker in refusal_markers)
    expects_refusal = bool(case.get("expect_refusal"))
    citation_present = citation_count > 0
    passed = (
        not forbidden
        and (refusal if expects_refusal else recall >= 0.66 and citation_present and not refusal)
    )
    return CaseScore(
        case_id=str(case["id"]),
        passed=passed,
        term_recall=round(recall, 3),
        citation_present=citation_present,
        refusal_detected=refusal,
        forbidden_term_hits=forbidden,
    )


def parse_sse(payload: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in payload.replace("\r\n", "\n").split("\n\n"):
        event = "message"
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


async def run_online(dataset: dict[str, Any], base_url: str, token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=120.0) as client:
        conversation_response = await client.post("/conversations", json={"title": "Automated evaluation"})
        conversation_response.raise_for_status()
        conversation_id = conversation_response.json()["id"]
        for case in dataset["cases"]:
            response = await client.post(
                "/chat/stream",
                json={"conversation_id": conversation_id, "content": case["question"]},
            )
            response.raise_for_status()
            events = parse_sse(response.text)
            errors = [data for event, data in events if event == "error"]
            if errors:
                raise RuntimeError(f"Evaluation case {case['id']} failed: {errors[-1]}")
            done = [data for event, data in events if event == "done"]
            citations = [data for event, data in events if event == "citation"]
            if not done:
                raise RuntimeError(f"Evaluation case {case['id']} produced no completed answer")
            answer = str(done[-1].get("content", ""))
            score = score_answer(case, answer, len(citations))
            results.append({"case": case, "answer": answer, "citations": citations, "score": asdict(score)})
    passed = sum(bool(item["score"]["passed"]) for item in results)
    return {
        "dataset_version": dataset["version"],
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the versioned Atlas grounded-answer evaluation suite.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--base-url", required=True, help="API URL including /api/v1")
    parser.add_argument("--token", required=True, help="Supabase user access token")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = asyncio.run(run_online(dataset, args.base_url, args.token))
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
