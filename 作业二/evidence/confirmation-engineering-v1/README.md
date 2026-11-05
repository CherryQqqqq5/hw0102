# 候选与交付控制工程验证

这些记录来自真实文件、容器和测试程序，模型请求数均为0，不计入正式任务成功率。

| 记录 | 验证对象 | 结果 |
|---|---|---|
| [controller/result.json](controller/result.json) | Aider原始与参考产物；候选证据升级；C0/C1保存恢复；既有测试和新增配置保护 | 全部通过 |
| [repository/result.json](repository/result.json) | 历史scikit-learn-14496补丁、40项公开测试；恢复后来修改的README，清除新建与暂存文件 | 全部通过 |
| [history/result.json](history/result.json) | 历史xarray修改后的证据失效、pytest既有测试修改、候选初始化失败后的独立评分 | 全部通过 |

短时限回归中，控制器在公开检查超时后恢复先前可行候选；最终阶段和模型主动验证两条路径分别约33.55秒和32.53秒完成，均小于62秒测试预算。普通提交路径也有40秒预算回归。

候选源文件及证据保存在各目录的`candidates/`；`controller.jsonl`给出实际检查、返回码、版本及恢复操作。已有任务产物的复用仅用于实现验收。原题正式评分仍由独立评分器产生。
