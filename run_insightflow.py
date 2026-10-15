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

TOPIC = (
    "研究检索增强生成（Retrieval-Augmented Generation）"
    "在制造业设备维护知识问答中的应用。"
    "搜索时使用简洁的英文关键词，围绕一个核心问题，"
    "初次搜索优先使用 retrieval augmented generation manufacturing maintenance，"
    "后续搜索针对资料中的信息缺口，不要堆砌多个场景。"
    "最终报告用中文，分为：来源支持的发现、"
    "对 MES 运维的应用建议、证据不足与待验证问题。"
    "每条来源支持的发现使用【来源：原始标题】标注，"
    "保留检索提供的标题，不自行补全被截断的标题。"
    "正文不要生成网址，原始链接由程序在报告末尾统一附上。"
    "厂商或项目作者的能力描述必须明确标注为自述，"
    "不得当作独立验证的效果。"
    "应用建议明确标注为建议，不得写成已验证事实。"
    "如果资料只有搜索摘要，明确说明未核对全文，"
    "不要推断摘要未提供的实验结果或效果数字。"
)


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
        "topic": TOPIC,
        "settings": settings,
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_status": git_output("status", "--short"),
        "code_sha256": code_fingerprint(),
        "status": "running",
        "completed_search_loops": 0,
        "completed_nodes": [],
        "timing_scope": "graph execution and local event logging; excludes key input",
    }

    final_report = None
    current_query = None
    failure = None
    start = perf_counter()

    print(f"\nStarting experiment: loops={args.loops}", flush=True)
    print(f"Output directory: {run_dir}", flush=True)

    try:
        with (run_dir / "events.jsonl").open("w", encoding="utf-8") as log:
            for event in graph.stream(
                {"research_topic": TOPIC},
                config={"recursion_limit": 30},
                stream_mode="updates",
            ):
                for node, update in event.items():
                    metadata["completed_nodes"].append(node)

                    if isinstance(update, dict):
                        if update.get("search_query"):
                            current_query = update["search_query"]

                        if node == "web_research":
                            metadata["completed_search_loops"] = update.get(
                                "research_loop_count", 0
                            )

                        if node == "finalize_summary":
                            final_report = update.get("running_summary")

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

        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if metadata["status"] == "success":
        (run_dir / "report.md").write_text(final_report, encoding="utf-8")
        print("\nReport saved:", run_dir / "report.md")
    else:
        print("\n" + failure)

    print("Status:", metadata["status"])
    print("Search loops:", metadata["completed_search_loops"])
    print("Elapsed seconds:", metadata["elapsed_seconds"])

    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()