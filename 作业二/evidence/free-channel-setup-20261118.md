# OpenRouter与Gemini免费接口配置

2026年11月18日。两项本地配置用于备用Application Programming Interface（API，应用程序编程接口），与hy4flash-free的270位置主评测独立。当前主评测不自动切换服务，不混合成绩。

## 本机连接

项目环境已安装keyring25.7.0，使用macOS系统钥匙串后端。脚本只读写本次指定的新条目：服务course-eval-free-openrouter及course-eval-free-gemini，账号course-eval-local。密钥不写入项目、配置文件、命令参数或日志；不访问其他钥匙串条目、浏览器凭据或账号密码。

```sh
work/.venv/bin/python scripts/setup_free_channels.py --serve
```

脚本在127.0.0.1的临时端口启动本次任务内的交互会话，并在Safari打开配置页；默认最多8小时，两项连接完成后结束。OpenRouter通过OAuth（Open Authorization，开放授权）及Proof Key for Code Exchange（PKCE，授权码交换证明密钥）连接，也接受用户在本机页面填写新密钥。Gemini需要用户在AI Studio创建免费项目密钥，在本机密码框填写。登录、条款及授权由用户本人操作。

OpenRouter回调校验随机state，授权码验证器仅在进程内存保存；拒绝跨来源表单、缺失会话标识和未列出的路径，页面禁止缓存，不记录HTTP（Hypertext Transfer Protocol，超文本传输协议）访问路径及表单。系统钥匙串保存后只读回同一新条目核对。

## 当前可核验状态

读取本机非敏感状态：

```sh
work/.venv/bin/python scripts/setup_free_channels.py --check
```

状态文件work/free-provider-setup/profiles.json只包含端点、钥匙串条目标识、认证状态、模型目录数量及费用验证状态。当前两个账号均等待用户登录，未创建或获取实际密钥，未发起备用服务模型推理。已有本机HTTP检查确认配置页返回200、包含两个表单并禁止缓存，跨来源提交返回403；三项非法元数据类型被结构校验拒绝。这些检查不构成账号认证成功或免费推理验证。

OpenRouter连接后通过官方/api/v1/key验证免费账号或零支出密钥限额，读取/api/v1/models筛选固定:free模型、输入和输出价格均为0、支持工具调用。每次实际推理仍须返回明确零费用，配置中的inference_enabled和actual_fee_verified在这之前保持false。Gemini连接只通过模型目录核验认证；用户勾选Free Tier仅记为用户确认，不能代替项目实际状态或逐次费用证明，推理同样保持禁用。

不设置付费账户、充值或自动补款。免费额度用尽或费用不明时停止，不切换到收费模型。

## 官方依据

- [OpenRouter官方授权流程](https://openrouter.ai/docs/guides/overview/auth/oauth)：支持本机回调，要求PKCE，并建议在桌面系统钥匙串保存密钥。
- [OpenRouter密钥状态接口](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key)：提供免费账号、密钥限额及免费日额度字段。
- [Gemini密钥说明](https://aistudio.google.com/docs/api-key)：新用户在接受条款后可获得默认项目和密钥，既有账号可能需要选择项目。
- [Gemini计费说明](https://aistudio.google.com/docs/billing)：免费层与付费项目分开，绑定计费账户及充值属于付费配置。
