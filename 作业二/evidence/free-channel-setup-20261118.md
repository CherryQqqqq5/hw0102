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

状态文件work/free-provider-setup/profiles.json只包含端点、钥匙串条目标识、认证状态、模型目录数量及费用验证状态。OpenRouter已认证，免费账号核验通过，认证时目录中有14个符合条件的模型，选择inclusionai/ling-3.2-flash:free，记录免费日剩余额度50；密钥已由连接页保存在指定系统钥匙串。真实推理及逐次费用尚未验证，inference_enabled和actual_fee_verified保持false。

用户授权直接操作后，已通过Safari的页面接口将既有Google Cloud项目导入AI Studio。项目显示“无法使用免费层级／受限”，没有免费项目验证入口。AI Studio原生项目创建提示必须在Cloud控制台创建；按官方普通项目流程建立了course-eval-free空项目，父级为无组织，未选择账单账户，资源列表确认后已导入AI Studio。该专用项目仍显示“无法使用免费层级／受限”，没有免费验证入口，空项目保留、未创建运行资源。当前未取得Gemini密钥，没有备用模型调用。Google官方说明受限项目换密钥不能恢复免费资格，升级账单将进入付费层；模型目录返回200也不能证明推理资格或免费状态。该状态与“Verification needed”手机验证分开。

已有本机HTTP检查确认配置页返回200、包含两个表单并禁止缓存，跨来源提交返回403；三项非法元数据类型被结构校验拒绝。当前连接服务已重新启动，地址http://127.0.0.1:63439；账号状态和实际免费推理分别核验，当前不切换主实验。

OpenRouter连接后通过官方/api/v1/key验证免费账号或零支出密钥限额，读取/api/v1/models筛选固定:free模型、输入和输出价格均为0、支持工具调用。每次实际推理仍须返回明确零费用，配置中的inference_enabled和actual_fee_verified在这之前保持false。Gemini连接只通过模型目录核验认证；用户勾选Free Tier仅记为用户确认，不能代替项目实际状态或逐次费用证明，推理同样保持禁用。

不设置付费账户、充值或自动补款。免费额度用尽或费用不明时停止，不切换到收费模型。

## 官方依据

- [OpenRouter官方授权流程](https://openrouter.ai/docs/guides/overview/auth/oauth)：支持本机回调，要求PKCE，并建议在桌面系统钥匙串保存密钥。
- [OpenRouter密钥状态接口](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key)：提供免费账号、密钥限额及免费日额度字段。
- [Gemini密钥说明](https://aistudio.google.com/docs/api-key)：新用户在接受条款后可获得默认项目和密钥，既有账号可能需要选择项目。
- [Gemini计费说明](https://aistudio.google.com/docs/billing)：免费层与付费项目分开，绑定计费账户及充值属于付费配置。
- [Gemini免费层受限说明](https://aistudio.google.com/docs/troubleshooting#free-tier-unavailable)：并非所有项目或账号都具备免费资格，受限项目换密钥无效；只读模型目录不能验证推理及计费资格。
- [Gemini项目验证说明](https://aistudio.google.com/docs/verification)：只有显示Verification needed等对应状态时按手机验证流程处理，当前项目实际显示Free tier unavailable。
- [Google Cloud普通项目创建](https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects)：项目创建与关联账单分开；本次仅建立不关联账单的空项目并核对免费资格。
