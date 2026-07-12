# 参与贡献

感谢你愿意改进 Leo AI Content Ops CN。

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
python -m unittest discover -s tests -v
```

Linux 或 macOS 可使用 `python -m pip install -e .`，Windows 通知属于可选能力。

## 提交要求

- 新行为先增加失败测试，再实现最小修复。
- 不提交真实 API Key、Cookie、平台账号或个人资料。
- 不提交 `wiki/`、`raw/`、生成稿件、日志和缓存。
- 涉及事实、平台能力或模型参数时，附上官方来源。
- Pull Request 说明应包含改动原因、用户影响和验证命令。

## 报告问题

普通缺陷和功能建议请创建 GitHub Issue。安全问题请遵循 [SECURITY.md](SECURITY.md)。
