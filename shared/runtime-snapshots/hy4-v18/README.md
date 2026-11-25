# Hy4 免费评测 v18 源代码快照

本目录保存同75题主方案和独立重复实际采用的课程层代码，与原运行目录 `work/frozen-performance-hy4-sql-layout-v18` 逐文件一致。72个源文件及固定的 sqlparse 依赖包共73个执行资源的 SHA-256 摘要和字节数见 `SOURCE_MANIFEST.json`；该清单也保存对应主方案的原计划摘要。

三组比较分别为主方案、原生 DeepSeek Harness（DSH，DeepSeek 智能体执行框架）及独立重复，每组75题，三个基准各25题。DSH 按其实际登记的运行版本逐题保存，不能用本目录的版本替换旧运行归属。五处局部修订另有各自的固定计划、公开检查和新会话，成绩与开发成本分别统计。

每题预算为500次实际模型请求、3,600秒交互、120秒命令、64,000输出词元和0次超时重试。模型限定为 `hy4flash-free`，每笔实际调用必须取得属于本次生成的零积分回执；缺失用量、身份或费用均停止，实际非零也停止。该源码快照不包含账户凭据，且不表示完整评测已结束。

运行环境使用 Python 3.13.12、mini-SWE-agent 2.4.6 和原题固定容器镜像。第三方依赖、任务数据、原评分与平台准备见[共用复现说明](../../README.md)。重新调用模型需要单独配置已核实的免费账户；只核对源码无需账户、网络或容器。

在本目录执行以下只读核查，可验证文件摘要及 Python 语法：

```sh
python -c 'from pathlib import Path; import hashlib,json; m=json.loads(Path("SOURCE_MANIFEST.json").read_text()); ok=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==v["sha256"] for n,v in m["files"].items()); print("source hashes match:",ok); raise SystemExit(0 if ok else 1)'
python -c 'from pathlib import Path; [compile(p.read_text(),str(p),"exec") for p in Path("course_eval").rglob("*.py")]; print("Python syntax verified")'
```
