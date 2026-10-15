import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from getpass import getpass
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parent

TOPIC = "研究检索增强生成（Retrieval-Augmented Generation）在制造业设备维护知识问答中的应用。"



def git_output(*args):
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def code_fingerprint():
    paths = [
        ROOT / "run_insightflow.py",
        ROOT / "pyproject.toml",
        *sorted((ROOT / "src" / "ollama_deep_researcher").glob("*.py")),
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, choices=[1, 2], required=True)
    parser.add_argument("--topic", default=TOPIC)
    args = parser.parse_args()

    settings = {
        "LLM_PROVIDER": "openrouter",
        "LOCAL_LLM": "nvidia/nemotron-3.5-lightning:free",
        "USE_TOOL_CALLING": "true",
        "SEARCH_API": "duckduckgo",
        "MAX_WEB_RESEARCH_LOOPS": str(args.loops),
        "FETCH_FULL_PAGE": "false",
    }
    os.environ.update(settings)

    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        os.environ["OPENROUTER_API_KEY"] = getpass(
            "Paste OpenRouter API key (hidden): "
        ).strip()

    if not os.environ["OPENROUTER_API_KEY"]:
        raise ValueError("API key is empty.")

    from ollama_deep_researcher.graph import graph

    run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = ROOT / "outputs" / "evaluation" / f"{run_id}_loops{args.loops}"
    run_dir.mkdir(parents=True)

    metadata = {
        "run_id": run_id,
        "started_at": datetime.now().astimezone().isoformat(),
        "topic": args.topic,
        "settings": settings,
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_status": git_output("status", "--short"),
        "code_sha256": code_fingerprint(),
        "status": "running",
        "version": "0.2",
        "completed_search_loops": 0,
        "completed_nodes": [],
        "timing_scope": "graph execution and local event logging; excludes key input",
    }

    final_report = None
    source_registry = []
    current_query = None
    failure = None
    start = perf_counter()

    print(f"\nStarting experiment: loops={args.loops}", flush=True)
    print(f"Output directory: {run_dir}", flush=True)

    try:
        with (run_dir / "events.jsonl").open("w", encoding="utf-8") as log:
            for event in graph.stream(
                {"research_topic": args.topic},
                config={"recursion_limit": 30},
                stream_mode="updates",
            ):
                for node, update in event.items():
                    metadata["completed_nodes"].append(node)

                    if isinstance(update, dict):
                        if update.get("search_query"):
                            current_query = update["search_query"]

                        if node == "web_research":
                            source_registry = update.get("source_registry", [])
                            metadata["completed_search_loops"] = update.get(
                                "research_loop_count", 0
                            )

                        if node == "finalize_summary":
                            final_report = update.get("running_summary")
                            metadata["citation_check"] = update.get("citation_check", {})

                    record = {
                        "node": node,
                        "elapsed_seconds": round(perf_counter() - start, 3),
                        "current_query": current_query,
                        "update": update,
                    }
                    log.write(
                        json.dumps(record, ensure_ascii=False, default=str) + "\n"
                    )
                    log.flush()

                    print(f"[Completed] {node}", flush=True)
                    if isinstance(update, dict) and update.get("search_query"):
                        print("Query:", current_query, flush=True)

        if not final_report:
            raise RuntimeError("No final report returned.")

        (run_dir / "report.md").write_text(final_report, encoding="utf-8")
        (run_dir / "citation-check.json").write_text(
            json.dumps(metadata.get("citation_check", {}), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metadata["status"] = "success"

    except KeyboardInterrupt:
        metadata["status"] = "interrupted"
        metadata["error_type"] = "KeyboardInterrupt"
        failure = "Run interrupted."

    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error_type"] = type(exc).__name__
        # Do not persist raw API error messages, which may contain sensitive data.
        failure = f"Run failed: {type(exc).__name__}"

    finally:
        metadata["elapsed_seconds"] = round(perf_counter() - start, 3)
        metadata["finished_at"] = datetime.now().astimezone().isoformat()

        (run_dir / "sources.json").write_text(
            json.dumps(source_registry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if metadata["status"] == "success":
        print("\nReport saved:", run_dir / "report.md")
    else:
        print("\n" + failure)

    print("Citation check:", metadata.get("citation_check", {}).get("status", "unavailable"))
    print("Status:", metadata["status"])
    print("Search loops:", metadata["completed_search_loops"])
    print("Elapsed seconds:", metadata["elapsed_seconds"])

    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()