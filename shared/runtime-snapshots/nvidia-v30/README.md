# NVIDIA 免费后端 v30 源代码快照

本目录保存2026年11月25日实际执行的课程层代码，与原运行目录 `work/frozen-performance-free-v30` 逐文件一致。78个执行资源文件的 SHA-256 摘要和字节数见 `SOURCE_MANIFEST.json`；其中包含固定版本的 sqlparse 依赖包。对应预登记方案的摘要为 `c0fe4961f310f979bec7da1101e75f0b86db240cb5b40364ccd76f4e2b528f18`。

本版在共用模型请求入口加入短动作指导：建议每条命令少于4096字符，长文件分段写入；需要自包含交付时，可以用短命令复制允许复用的代码。mini-SWE-agent 与原生 DeepSeek Harness（DSH，DeepSeek 智能体执行框架）经过同一个消息变换。4096字符是提示目标；工具参数约束、本地校验、模型、采样、64,000输出词元、500次实际请求、3,600秒整题预算及费用检查沿用原设置。

费用验证采用已核实的 NVIDIA 官方免费端点政策与每次响应的实际身份、模型和完整用量。缺失金额保持 `null`，不以本地错误事件代替模型回执。新的费用缺口、身份或用量不明确以及实际非零金额会阻断新请求。

该快照对应三组各一条 ReLU 原题的有界验证准入。实际成绩、完整75题比较及最终报告由各自的原题评分和证据索引确认，源码快照本身不表示这些评测已经完成。旧尝试及其费用缺口独立留存。

本机实际使用 Python 3.13.12、mini-SWE-agent 2.4.6、OpenAI Python SDK（Software Development Kit，软件开发工具包）3.45.0、Pydantic 2.14.2 和 Requests 2.34.2。原生 DSH 在任务容器中使用已固定的0.2.2rc2版本。第三方依赖、任务数据、原镜像及容器运行环境按[共用说明](../../README.md)和对应执行清单准备。

在本目录核对源文件摘要和 Python 语法，可运行以下命令；它只读源文件，不导入执行模块：

```bash
python -c 'from pathlib import Path; import hashlib,json; m=json.loads(Path("SOURCE_MANIFEST.json").read_text()); ok=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==v["sha256"] for n,v in m["files"].items()); print("source hashes match:",ok); raise SystemExit(0 if ok else 1)'
python -c 'from pathlib import Path; [compile(p.read_text(),str(p),"exec") for p in Path("course_eval").rglob("*.py")]; print("Python syntax verified")'
```
