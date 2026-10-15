# v0.2 更新操作

这是覆盖更新包，适用于你当前的 InsightFlow 项目，不是独立完整仓库。保留原项目其余文件与许可证。依赖不变。

1. 将 zip 下载到 Windows 下载目录。关闭正在运行的研究进程。
2. 在项目 PowerShell 执行备份和解压（按实际下载文件名调整路径）：

```powershell
Set-Location "$env:USERPROFILE\Projects\InsightFlow-Lab\local-deep-researcher"
$backup = ".\outputs\backup-before-v02-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item .\src -Destination $backup -Recurse
Copy-Item .\run_insightflow.py -Destination $backup
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\insightflow-v0.2-update.zip" -DestinationPath . -Force
```

3. 离线验证，不需要 API key：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_v02.py -v
```

预期 6 个测试通过。若依赖导入失败，把错误发回，先不要修改依赖版本。

4. 在线运行：

```powershell
.\.venv\Scripts\python.exe .\run_insightflow.py --loops 1
```

预期顺序：generate_query、web_research、summarize_sources、finalize_summary。等待超过 15 秒会显示 Waiting。报告目录包含 report.md、sources.json、citation-check.json、metadata.json、events.jsonl。执行 success 与引用检查 passed 是两回事。

检查报告中 [S1] 等编号是否对应 sources.json，并人工判断摘要是否支持论断。确认后可再运行 --loops 2，预期中间只有一次 reflect_on_summary。

5. 按 docs/v0.2-changes.md 的建议更新根 README，添加审阅后的实际示例。提交前执行：

```powershell
git add -- run_insightflow.py src/ollama_deep_researcher/graph.py src/ollama_deep_researcher/state.py src/ollama_deep_researcher/prompts.py src/ollama_deep_researcher/sources.py src/ollama_deep_researcher/progress.py tests/test_v02.py tests/fixtures/two-loops-events.jsonl docs/v0.2-changes.md UPDATE-v0.2.md README.md
git --no-pager diff --cached --check
git --no-pager diff --cached --stat
git --no-pager diff --cached
```

检查暂存内容后提交并推送：

```powershell
git commit -m "Add source registry, citation checks and research progress feedback"
git push origin insightflow-dev:main
```

不要使用 git add . 将临时测试脚本或其他文件一并提交。若添加实测示例，使用具体路径单独 git add。这里没有替你提交或推送。
