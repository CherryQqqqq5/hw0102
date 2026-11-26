# 报告生成与提交包

`render_hy4_final_reports.py`生成两份正式PDF，读取已完成的75题数据和33次输入效率对照。它在保留原始运行文件的工作目录中核对来源摘要；该原始目录保存在ModelArts。

`report_input_efficiency.py`组织新增实验的设置、结果与分析。`render_course_phase_reports.py`统一黑体、字号与重点加粗；字体路径使用`COURSE_HEITI_LIGHT`、`COURSE_HEITI_BOLD`指定。文档依赖的实际版本见`requirements.txt`。

`verify_report_layout.py`逐页检查文本、字体和页界并生成渲染图，正式交付前逐页目视核对。`package_final_submission.py`使用固定Git提交和GitHub两份PDF的实际字节回执生成提交包，校验ZIP及全部成员。`submission_readme.py`根据真实结果生成包内说明。

`interruption_cost.py`使用模型运行环境中的原生回执校验规则复核追加尝试的费用账本，保留未知费用与停止状态；该尝试单独记录。

发布证据目录各自提供离线复算原评分、词元、调用和费用回执的入口；离线复核使用保存的记录。
