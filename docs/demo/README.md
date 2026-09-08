# Excel 演示

本目录的工作簿和 PNG 使用 `examples/demo.json` 中的虚构岗位、候选人证据，经过真实 SQLite、评分和工作台导出流程生成。没有使用个人岗位库或真实简历。

## 如何查看

- `workspace.xlsx`：完整五个工作表。主表展示 3 个岗位，过滤表保留 2 个岗位。
- `workspace.png`：主表 A1:M8 区域的工作表渲染图，不是 Excel 应用窗口截图。
- `filtered.png`：过滤记录工作表渲染图。
- `results.md`：逐项评分与预置简历方案。

演示版简历入口不包含链接，避免公开工作簿误操作读者的本地服务。没有更新运行、永久隐藏或投递记录的表明确展示空状态。星级不是录用概率。时间列是演示运行时间，不是招聘发布时间。

## 重建

核心离线演示不需要模型或表格运行时：

```bash
.venv/bin/job-agent demo
```

Excel 导出另需 Codex 捆绑的 `@oai/artifact-tool`，与正式导出使用相同依赖；目前不是普通 npm 安装即可复现的功能。配置 `JOB_AGENT_NODE`（Node 可执行文件）和 `JOB_AGENT_NODE_MODULES`（捆绑模块目录）后，在仓库根目录运行：

```bash
demo_dir=$(.venv/bin/job-agent demo)
runner_dir=$(mktemp -d)
ln -s "$JOB_AGENT_NODE_MODULES" "$runner_dir/node_modules"
cp scripts/build_workspace.mjs "$runner_dir/build_workspace.mjs"
"$JOB_AGENT_NODE" "$runner_dir/build_workspace.mjs" "$demo_dir/workspace.snapshot.json" "$demo_dir/workspace.xlsx" "$demo_dir/previews"
```

每次 demo 创建独立目录。导出器读取其中的快照，不读取真实数据库。生成文件留在该目录，不自动覆盖这里的公开展示文件。日期会随重建变化。

## 本次验收

2026-09-08：36 项 Python 测试通过；表格引擎重算后的主表统计为展示 3、五星 2、待确认 2，与输入记录核对一致；公式错误扫描无匹配。五个工作表已渲染并检查中文、空状态和资格标注。未验证 Microsoft Excel 应用内的交互行为，不将渲染结果等同于原生应用验收。

Excel 中仅保存虚构数据和 `.invalid` 来源链接。公开发布前仍需对整个 Git 历史另做隐私审查。
