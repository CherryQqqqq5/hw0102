# 2026年11月25日课程复现代码

本目录保存当前实际编排、分析、导出、公开检查和报告代码，以及被冻结程序按路径加载的运行时源码。它是独立代码与输入来源目录，不是完整实验结果或最终提交包；两份正式PDF和完整主结果尚未完成。本目录没有复制模型轨迹、在途会话、隐藏评分输入、镜像、SDK大树、凭据、STOP或账户元数据。

`SOURCE_MANIFEST.json`分别记录原文件的source SHA-256摘要与发布文件的export SHA-256摘要。代码保持原字节，配置记录仅使用已有`export_performance_evidence.scrub`脱敏。含`[project]`等替换标记的计划用于核对原运行来源，不能直接充当新的执行准入。完整运行证据由独立的既有导出器保留；不能从这里缺少原始run目录推断费用为零或任务已通过。

## 目录和已发布源码

以本目录作为工作根，保留原`course_eval/`、`scripts/`与`work/`相对布局。Hy4 v18和NVIDIA v31的源码也按实际导入路径提供，内容与上级`runtime-snapshots/`内既有版本对应；本次补齐NVIDIA v27、原DSH基线、FEAL v19和guidance-off四个必须区分的版本。NVIDIA v27 reader明确检查实际模块文件路径，因此不能用v31路径替换它。

六个运行时的完整资源清单保存在manifest中。已有公开sqlparse wheel不在此重复复制，manifest明确标注其上级已发布文件和摘要。Linux SDK、Python二进制、容器镜像等外部执行资源不在此目录。原文件集合和已复制源码集合不是同一统计口径。

## 离线核对

在已安装对应依赖的Python 3.13环境中，从本目录执行：

```sh
python sync_sources.py verify
python work/parallel-free-evaluation-20261124/export_nvidia_v28.py --help
python work/parallel-free-evaluation-20261124/export_nvidia_history.py --help
python work/parallel-free-evaluation-20261124/prepare_report_data.py --help
python work/nvidia75-parallel-dispatch-v32-20261125/benchmarks_entry.py --import-proof
```

既有脱敏证据包放在本目录之外，使用`export_nvidia_v28.py verify --out <包路径>`或`export_nvidia_history.py verify --out <历史包路径>`重算。验证保留原题通过、未通过及无分中断、原生身份与费用缺口。NVIDIA缺金额继续为`null`；OpenRouter缺自身回执不能用账户累计零替代。本目录不附新的证据包，也不重新运行模型或原评分器。

`work/parallel-free-evaluation-20261124/requirements-execution-20261125.txt`是当时136包的执行环境清单，不等于136包均完成独立clean安装。此前82包分析环境及增加5项依赖后的87包离线资格具有各自范围，具体以已有资格记录为准。第三方依赖安装及新的隔离环境尚需在目标平台另行验证。

## Harbor原生产物采集入口

`launchers/harbor_entry.py`保留实际自定义启动程序的`prepare_args -> Harbor app`调用，删除机器专用shebang，并用本地目录查找代替固定层数，便于源码目录和本地venv两种位置使用。此文件名避免遮蔽已安装的`harbor`包。原577字节启动程序的摘要与本适配文件摘要分别记录。`python launchers/harbor_entry.py --help`只检查CLI入口。

标准安装Harbor不会自动加入这个采集入口。若在自己的环境执行新实验，应在自己venv的Harbor入口安装该适配程序及本机解释器shebang，再对新的launcher和capture policy进行原有零模型资格与独立准入。旧策略中的launcher摘要仍描述当时实际程序，不能悄悄更新旧计划或复用旧审核。复制源码不授权新模型请求或费用事件接受。

## 模型与评分执行的外部条件

当前Hy4最终原批次和其局部修订、NVIDIA辅助队列分别保留实际版本，不合并成同模型新成绩。NVIDIA六个继承分的来源是v27 ELF三次、v30 mini ReLU两次（含主方法失败）和v31 DSH ReLU一次；v32只调整服务间排队和共享资源池调度，其余219个位置不因代码发布而视为已运行。

新执行需要另备公开题目数据与各自固定提交、原镜像pin、Docker/Lima、当前可用的模型身份和费用资格；所有费用停止与每笔验费规则保持。图像下载可选准备入口`image_copy_proxy_cdn.py`只描述额外的公开CDN路由，未被伪称为原1100项冻结绑定的一部分。不得从此目录恢复原账户的接受计数或解除真实STOP。

原生DeepSeek Harness（DSH，DeepSeek智能体执行框架）使用0.2.2rc2，来源为`https://github.com/deepseek-ai/deepseek-harness/tree/dsh-v0.2.2-rc.2`；运行时另有Python 3.13.12及amd64/arm64安装。`dsh-runtime-files.json`保存9840个实际文件摘要和2046个链接目标；它是来源与完整性描述，不是SDK二进制。已有amd64实际初始化资格不等于此处重新验证了全部平台。数据和Docker准备方式可参阅上级`shared/README.md`，但其旧实验预算不能覆盖本次计划。

## PDF与最终交付边界

`render_hy4_final_reports.py`、共同样式`render_course_phase_reports.py`和原作业一renderer均保留。样式当前需要macOS的Arial Unicode字体；系统字体没有随代码分发。Linux重建应另备具有相应许可和字形覆盖的字体并单独核验版式，不能把本机字体检查当作跨平台通过。

原作业一renderer还依赖既有诊断统计、任务记录；最终报告需要本轮真实report-data和准确独立审核。它们不在本次代码同步范围。`package_final_submission.py`继续要求完整原225、消融与最终资格及准确审核来源；NVIDIA辅助partial不被冒称完整结果。最终Git提交、两PDF字节一致性、脱敏证据、ZIP和下载入口由最终交付环节另行核验。

本机报告入口的实际现成环境另有ReportLab 4.4.9、pdfplumber 0.11.9、Pillow 13.0.0、pypdf 6.21.4及Poppler `pdftoppm` 25.05.0；这些报告依赖不在主执行venv的完整安装资格内。本次只使用既有环境验证renderer的`--help`，未安装依赖、生成新PDF或重新进行视觉验收。

## 作者同步范围

维护者仅在原工作区明确选择源根后执行`sync_sources.py sync --source-root <原项目根>`。允许清单不遍历任何新v32队列，也不跟随计划的`all_files_sha256`去复制原始私有来源。只读静态import闭包用于补齐本地课程模块；不安装依赖、不启动容器、不读取Keychain。源变化会显式失败，不自动覆盖已同步版本。
