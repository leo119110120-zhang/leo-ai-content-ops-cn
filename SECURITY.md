# Security Policy

## Supported version

当前仅维护最新的 `main` 分支。

## Reporting a vulnerability

请优先使用 GitHub 仓库 Security 页面中的 **Report a vulnerability** 私密报告入口。不要在公开 Issue 中粘贴 API Key、Cookie、Token、个人资料或可利用细节。

报告中请包含：受影响版本、最小复现、潜在影响和建议修复。收到报告后会先确认影响范围，再决定修复与披露节奏。

## Secret handling

- DeepSeek Key 只从 `DEEPSEEK_API_KEY` 环境变量读取。
- 平台密码、Cookie、OTP 和登录 Token 不属于本项目配置。
- 本地 HTTP 服务只绑定 `127.0.0.1`。
- `raw/` 原始资料只读，真实输入默认被 Git 排除。
