# 候选文件名编码回归

相邻`candidate-locale-before-v1/`在原Django-11999镜像复现了与正式失败相同的`UnicodeDecodeError`。修复在候选文件助手进程前设置`LC_ALL=C.UTF-8`，模型命令、公开检查和评分环境保持原设置。

本目录`result.json`记录10个SWE原镜像的实际验证：初始化成功；非ASCII文件名能够保存、修改及恢复；恢复初始候选后新增文件被清除；待验证证据仍为pending，没有被提升为通过。每个镜像保留候选内容与操作记录。模型请求数为0，工程用例不计入原题任务成功率。

从`shared/`执行以下命令可在已准备的原镜像中重跑：

```sh
PYTHONPATH=. work/.venv/bin/python scripts/check_candidate_locale.py \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --out work/vmshare/candidate-locale-recheck
```

脚本旁两份文本文件为明确标记的工程输入，验证文件字节恢复。原仓库内已有非ASCII路径触发了真实初始化错误，工程输入进一步检查保存和恢复路径，避免仅修复读取输出而遗漏文件操作。
