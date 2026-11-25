# CodeBuddy 2.179.3：实际免费通道客户端补丁

本目录提供当前 Hy4 评测使用的 CodeBuddy 命令行接口（Command-Line Interface，CLI）补丁。它对应 npm 软件包 `@tencent-ai/codebuddy-code@2.179.3` 的 `dist/codebuddy-headless.js`，与较早的 v11 响应补丁分别保留。评测计划中的 `client_sha256` 及本目录清单记录同一份实际客户端。

| 文件或校验对象 | SHA-256 |
|---|---|
| 原始 `dist/codebuddy-headless.js` | `abe2d02f74f208b4ea7a0c8621fb7c7cf5822ef6d88af7cf413a6de820a987a4` |
| 实际补丁后的客户端 | `bfc167075d229f101878a378e6c5f9a8c2b64463545dd5ffb3881d6417040915` |
| `codebuddy-free-safety.patch` | `90d71c55049e3a90e6bb8179ae0c054314c8409d340862b7fe6500b383834b7e` |

安装原版本后，先确认原始文件摘要；在该 npm 软件包的根目录执行 `patch --batch -p1 -i /绝对路径/codebuddy-free-safety.patch`，再核对补丁后的文件摘要并执行 `node --check dist/codebuddy-headless.js`。不同版本或摘要不符时停止，不能继续套用。本补丁不包含完整 npm 依赖、登录状态或账户凭据。

补丁使外部评测程序能够控制实际生成次数、续接预算和明确本地错误的最终序列化；通过环境变量 `COURSE_CODEBUDDY_EXTERNAL_RECOVERY=1` 启用相应行为。每次实际请求的模型身份及零积分仍由评测程序的 `codebuddy_free.py` 独立核验。缺少费用回执的上游错误继续记为未知并停调，补丁不为缺失回执补零，也不自动切换收费模型。

原清单记录了真实原文件重建、补丁后摘要及 Node.js 语法检查。本次同步重新核对原文件、补丁、清单和正在使用的客户端摘要一致，未重新调用模型。这个客户端补丁是运行依赖，不能作为完整75题评测、改造收益或最终报告已经完成的证据。
