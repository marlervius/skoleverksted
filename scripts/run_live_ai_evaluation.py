"""Opt-in real-model contract smoke test.

This is deliberately small and supplemental. It stores only timings, parser
status and counts; it never persists model output, prompts or user data.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from Skoleverksted.backend.platform.quality_runtime import run_bounded_sync


def _parse_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-calls", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--model", default=os.getenv("GOOGLE_MODEL", "gemini-3.5-flash"))
    parser.add_argument("--report", type=Path, default=Path("output/test-runs/live-ai-evaluation.json"))
    args = parser.parse_args()
    if args.max_calls < 1 or args.max_calls > 5:
        parser.error("--max-calls må være mellom 1 og 5")
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        parser.error("GOOGLE_API_KEY mangler; live AI er opt-in og krever egen testnøkkel")

    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - dependency is optional locally
        parser.error(f"google-genai mangler: {exc}")

    cases = json.loads(Path("Skoleverksted/backend/evals/quality_cases.json").read_text(encoding="utf-8"))[: args.max_calls]
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    results = []
    for case in cases:
        request = case["request"]
        prompt = (
            "Du er en testagent. Returner kun JSON med nøklene claims og sources. "
            "claims skal være en liste med claim og status. Bruk dette syntetiske skoleeksempelet:\n"
            f"Fag: {request.get('module')}\nNivå: {request.get('title')}\nTekst: {request.get('content', '')}"
        )
        started = time.monotonic()
        try:
            response = run_bounded_sync(
                lambda: client.models.generate_content(model=args.model, contents=prompt),
                timeout_seconds=args.timeout,
                operation_name="live AI evaluation call",
            )
            parsed = _parse_json(getattr(response, "text", "") or "")
            results.append(
                {
                    "name": case["name"],
                    "status": "parsed" if parsed is not None else "invalid_json",
                    "claims": len(parsed.get("claims", [])) if parsed else 0,
                    "sources": len(parsed.get("sources", [])) if parsed else 0,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            )
        except Exception as exc:  # no provider details or response text in report
            results.append(
                {
                    "name": case["name"],
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                }
            )

    report = {
        "suite": "live_ai_contract_smoke",
        "model": args.model,
        "max_calls": args.max_calls,
        "status": "passed" if all(item["status"] == "parsed" for item in results) else "failed",
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
