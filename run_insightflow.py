import os
from datetime import datetime
from getpass import getpass
from pathlib import Path

# 显式设置配置，避免旧环境变量影响本次运行。
os.environ.update({
    "LLM_PROVIDER": "openrouter",
    "LOCAL_LLM": "nvidia/nemotron-3.5-lightning:free",
    "USE_TOOL_CALLING": "true",
    "SEARCH_API": "duckduckgo",
    "MAX_WEB_RESEARCH_LOOPS": "1",
    "FETCH_FULL_PAGE": "false",
})

if not os.environ.get("OPENROUTER_API_KEY", "").strip():
    os.environ["OPENROUTER_API_KEY"] = getpass(
        "Paste OpenRouter API key (hidden): "
    ).strip()

from ollama_deep_researcher.graph import graph

topic = (
    "研究检索增强生成（Retrieval-Augmented Generation）"
    "在制造业设备维护知识问答中的应用。"
    "搜索时使用简洁的英文关键词，围绕一个核心问题，"
    "优先使用 retrieval augmented generation manufacturing maintenance，"
    "不要堆砌多个场景。"
    "最终报告用中文，分为：来源支持的发现、"
    "对 MES 运维的应用建议、证据不足与待验证问题。"
    "每条来源支持的发现使用【来源：原始标题】标注，"
    "保留检索提供的标题，不自行补全被截断的标题。"
    "正文不要生成网址，原始链接由程序在报告末尾统一附上。"
    "厂商博客中的能力描述必须标注为厂商自述，"
    "不得当作独立验证的效果。"
    "应用建议明确标注为建议，不得写成已验证事实。"
    "如果资料只有搜索摘要，明确说明未核对全文，"
    "不要推断摘要未提供的实验结果或效果数字。"
)

node_labels = {
    "generate_query": "生成搜索词",
    "web_research": "检索网页",
    "summarize_sources": "总结搜索资料",
    "reflect_on_summary": "识别信息缺口",
    "finalize_summary": "整理最终报告",
}

final_report = None

print("\n开始研究：", topic, flush=True)

for event in graph.stream(
    {"research_topic": topic},
    config={"recursion_limit": 20},
    stream_mode="updates",
):
    for node, update in event.items():
        print(
            f"\n[完成] {node_labels.get(node, node)}",
            flush=True,
        )

        if not isinstance(update, dict):
            continue

        if update.get("search_query"):
            print("搜索词：", update["search_query"], flush=True)

        if node == "web_research":
            print(
                "已搜索轮数：",
                update.get("research_loop_count"),
                flush=True,
            )
            for source in update.get("sources_gathered", []):
                print("来源：", source, flush=True)

        if node == "finalize_summary":
            final_report = update.get("running_summary")

if not final_report:
    raise RuntimeError("流程未返回最终报告，请检查上方输出。")

output_dir = Path(__file__).resolve().parent / "outputs"
output_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_path = output_dir / f"mes_rag_report_{timestamp}.md"
report_path.write_text(final_report, encoding="utf-8")

print("\n报告已保存：", report_path)
print("\n报告预览：\n")
print(final_report[:1500])