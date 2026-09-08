# 自动测试说明

工作流：[ci.yml](../.github/workflows/ci.yml)。推送、PR 和手动触发时，在 Ubuntu 与 macOS 的 Python 3.13 环境执行：

1. 将 pip 升至 `>=26.2.1,<27`，从 `pyproject.toml` 安装项目及开发依赖，运行 `pip check`。
2. 执行 Python 测试，输出 JUnit 报告。
3. 严格执行评分挑战集：存在未满足预期时返回失败。
4. 运行虚构离线演示，验证命令行入口及生成流程。
5. 保存测试和评测报告 7 天。测试失败时仍尝试生成评测结果并保留报告，不把失败改成成功。

## 安全范围

仅使用 GitHub 官方 Actions，并固定为已核实的完整提交 SHA。仓库令牌只有读取代码权限，checkout 不保存凭据。使用普通 `pull_request`，不使用高权限 `pull_request_target`。没有配置 Secrets、API Key、招聘账号或钥匙串访问，没有部署、发布或自动提交代码步骤。

上传清单仅包含 JUnit、评测 JSON 与 Markdown；不上传整个 `data/`、数据库、简历、工作簿或日志目录。运行依赖安装会访问 Python 包源，测试及离线演示不需要招聘平台和模型服务。此配置不替代发布前对 Git 历史的隐私审查。

## 能证明什么

可以检查核心服务、数据处理、规则评分、简历确认门与离线演示的工程回归。不能证明真实推荐准确率，也不覆盖 Excel 原生交互、DOCX/PDF 视觉排版、macOS 钥匙串集成或浏览器操作。

本地验证不等于 GitHub 托管执行。仓库尚未推送，本阶段不显示绿色 CI 徽章；首次上传后需进入 Actions 确认两个系统的运行结果，并下载报告检查。分支保护也需仓库创建后单独配置。

Python 第三方依赖仍按项目声明的版本范围解析，未生成锁文件，因而不承诺逐包完全可复现；完整依赖锁定与升级策略属于后续发布检查。Actions SHA 更新也应审核后提交。

配置参考：[GitHub Python 测试指南](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) 与 [setup-python 官方文档](https://github.com/actions/setup-python/blob/main/README.md)。
