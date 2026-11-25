# NVIDIA 免费后端 v31 源代码快照

本目录保存2026年11月25日实际执行的课程层代码，与原运行目录 `work/frozen-performance-free-v31` 逐文件一致。78个执行资源文件的 SHA-256 摘要和字节数见 `SOURCE_MANIFEST.json`；其中包含固定版本的 sqlparse 依赖包。模型运行时对应v31修复计划 `0995b63b9b2d06cef8a4348872a7757941c13c8fc1419a2da5b5c133e0dd4da3`，当前并行续跑计划为 `f5971565bd5b18374b065f0b2aeb7659727310beef85a0e375b9fd18c9f7dae2`。

本版沿用v30的共同短动作指导，并将原生 DeepSeek Harness（DSH，DeepSeek 智能体执行框架）桥接的空闲等待期限对齐整题期限。此前客户端在费用完整响应返回前因930秒空闲限制退出，随后回写触发BrokenPipe。改动仅在 `dsh_runner.py` 增加显式空闲设置，其他77个资源与v30逐字节一致。mini-SWE-agent 与原生DSH继续共用短命令和分段交付指导；4096字符仍为提示目标，工具参数约束、本地校验、模型、采样、64,000输出词元、500次实际请求、3,600秒整题预算及费用检查保持。

费用验证采用已核实的 NVIDIA 官方免费端点政策与每次响应的实际身份、模型和完整用量。缺失金额保持 `null`，不以本地错误事件代替模型回执。新的费用缺口、身份或用量不明确以及实际非零金额会阻断新请求。

修复后的DSH ReLU已取得真实原题通过评分和16份完整免费政策证明。该次运行没有最终SDK completed标记，最长完整模型响应约645.8秒；不能据此声称已在云端实测超过旧930秒等待，也不能把代码快照当作完整75题比较结果。v32仅调整服务间排队，原共享资源池仍为最多两道轻任务或一道独占任务。三组共六个已有原评分保留其实际v27、v30、v31来源，其余219个位置沿用本目录实现；原主方案ReLU失败及旧无分中断继续保留。完整成绩和正式报告由最终证据索引确认。

本机实际使用 Python 3.13.12、mini-SWE-agent 2.4.6、OpenAI Python SDK（Software Development Kit，软件开发工具包）3.45.0、Pydantic 2.14.2 和 Requests 2.34.2。原生 DSH 在任务容器中使用已固定的0.2.2rc2版本。第三方依赖、任务数据、原镜像及容器运行环境按[共用说明](../../README.md)和对应执行清单准备。

在本目录核对源文件摘要和 Python 语法，可运行以下命令；它只读源文件，不导入执行模块：

```bash
python -c 'from pathlib import Path; import hashlib,json; m=json.loads(Path("SOURCE_MANIFEST.json").read_text()); ok=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==v["sha256"] for n,v in m["files"].items()); print("source hashes match:",ok); raise SystemExit(0 if ok else 1)'
python -c 'from pathlib import Path; [compile(p.read_text(),str(p),"exec") for p in Path("course_eval").rglob("*.py")]; print("Python syntax verified")'
```
