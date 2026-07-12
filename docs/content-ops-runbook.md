# 内容运营自动化使用手册

## 首次安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
$key = Read-Host "请输入 DeepSeek API Key"
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", $key, "User")
Remove-Variable key
```

API Key 只存入当前 Windows 用户环境变量，不写入仓库。设置后重新打开 PowerShell。

## 手动验证

把 Markdown 放入 `wiki/`，或把临时资料放入只读目录 `raw/inbox/`：

```powershell
leo-content-ops daily --root .
```

流程会生成最多三个合格候选，并在本机 `127.0.0.1` 页面等待选择。选中后系统生成公众号稿、小红书稿、封面、图卡和质量报告，再进入人工终审。

真实 DeepSeek 请求可能产生 API 费用。首次运行前可先执行离线测试：

```powershell
python -m unittest discover -s tests -v
```

## 安装 10:30 计划任务

只有在手动真实运行成功后再安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-content-ops-task.ps1
Get-ScheduledTask -TaskName LeoContentOpsDaily
```

任务在周一至周五 10:30 运行；错过时间时由 Windows 在下次可用时补跑。

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/uninstall-content-ops-task.ps1
```

## 故障恢复

- 同一天已有完成回执时，不会再次请求模型。
- 电脑重启后会恢复未选择的候选页或未完成的终审页。
- 运行锁超过两小时视为异常中断；近期锁不会被抢占。
- DeepSeek 请求失败时回滚来源缓存，新来源会在下次重试。
- 日志位于 `content-ops/logs/`，只记录状态和错误类型。
- 自动质量检查失败时停止发布，保留任务供人工检查。

## 安全边界

- 本地服务只绑定 `127.0.0.1`。
- 不自动登录或发布公众号、小红书。
- 不保存平台密码、Cookie、OTP 或 Token。
- `raw/` 原始资料永不改写。
