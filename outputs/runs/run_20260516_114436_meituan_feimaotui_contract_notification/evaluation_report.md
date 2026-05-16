# 对话模型评测总报告

## 1. 总览

- 总 case 数：12
- 通过 case 数：6
- 通过率：50.0%
- 平均分：73.33
- P0 平均分：73.33
- P0 通过率：50.0%
- 一票否决 case 数：0
- 风险项数量：9

## 2. 分数分布

| 分数段 | case 数 |
|---|---:|
| 90-100 | 3 |
| 80-89 | 3 |
| 60-79 | 3 |
| 0-59 | 3 |

## 3. 维度得分

| 维度 | 权重 | 平均得分 | 得分率 | 主要失分原因 |
|---|---:|---:|---:|---|
| 合规性 | 10.0 | 10.00 | 100.0% | 无 |
| 异常处理能力 | 10.0 | 6.25 | 62.5% | 未出现异常场景，无需处理；对话中未触发任何异常场景，无需处理；未使用标准回复处理超出范围问题 |
| 表达质量 | 10.0 | 8.50 | 85.0% | 无 |
| 知识准确性 | 15.0 | 14.17 | 94.4% | 未给出单日/多日具体单量数值X和Y；未说明未完成单量要求的后果；未引用任何知识点，但无错误，故不扣分 |
| 流程执行度 | 25.0 | 15.00 | 60.0% | 未询问骑手配送意愿（步骤3）；未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| 任务完成度 | 30.0 | 22.50 | 75.0% | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未提醒骑手注意配送安全 |

## 4. Case 明细

| case_id | 总分 | 是否通过 | 一票否决 | 缺失覆盖项 | 主要结论 |
|---|---:|---|---|---|---|
| case_001 | 82.50 | 是 | 否 | 无 | 客服模型表现良好，核心任务全部完成，知识准确，合规无问题，表达质量高。主要不足在于流程执行度，缺失了询问配送意愿、解释报名机制和提供行为建议三个步骤，但骑手主动表示愿意配送且未触发相关异常，整体效果达标。 |
| case_002 | 95.00 | 是 | 否 | process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism | 该case整体表现优秀，核心任务全部完成，流程执行度较高，知识准确，合规无问题，异常处理得当，表达质量好。主要缺失为未解释报名排名机制和提供行为建议，但未影响核心目标达成。 |
| case_003 | 81.50 | 是 | 否 | task_goal_consecutive_days_requirement, task_goal_safety_reminder, process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism | 客服模型较好地完成了合同生效通知、单量要求说明和鼓励骑手等核心任务，但遗漏了安全提醒和连续天数要求（单日合同需连续Y天完成配送），也未解释报名排名机制和提供行为建议。知识引用准确，合规性良好，异常处理得当，表达质量符合要求。建议补充安全提醒和连续天数要求，并完善流程步骤。 |
| case_004 | 81.50 | 是 | 否 | 无 | 该case在任务完成度上完成了4项核心任务，仅遗漏安全提醒；流程执行度缺失安全提醒、报名机制解释和行为建议3个步骤；知识准确性无错误；合规性无禁止项；异常处理得当；表达质量良好。主要失分项为遗漏安全提醒，建议在对话中增加安全提醒话术。 |
| case_005 | 92.50 | 是 | 否 | 无 | 客服模型表现良好，完成了所有核心任务，流程执行度较高，知识准确，合规无问题，表达质量优秀。主要缺失步骤为询问配送意愿、解释报名机制和提供行为建议，但整体对话流畅，骑手理解并愿意开始配送，达到业务目标。 |
| case_006 | 40.50 | 否 | 否 | 无 | 该case中，站长完成了身份确认、合同生效通知和询问配送意愿，但未能给出具体单量数值X和Y，也未说明连续天数、安全提醒、报名机制和行为建议等关键信息。面对骑手多次追问，站长重复相同内容，未有效处理异常。整体表现较差，需重点改进知识准确性和异常处理能力。 |
| case_007 | 60.50 | 否 | 否 | task_goal_retention_and_encouragement, task_goal_safety_reminder, process_step_willingness_inquiry, process_step_registration_mechanism_explanation, process_step_behavior_suggestion | 该case中站长完成了合同生效通知、单量要求和连续天数要求等核心任务，但缺失了询问配送意愿、挽留鼓励、安全提醒、解释报名机制和提供行为建议等关键步骤。由于骑手不耐烦且主动挂断，站长未能完成全部流程。合规性良好，但遗漏安全提醒需扣分。建议在后续对话中主动询问骑手意愿并补充安全提醒。 |
| case_008 | 53.50 | 否 | 否 | task_goal_daily_minimum_order_requirement, task_goal_consecutive_days_requirement, task_goal_retention_and_encouragement, task_goal_safety_reminder, process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_additional_reward | 该case中客服模型仅完成了身份确认、合同生效告知和配送意愿询问，未涉及单量要求、连续天数、安全提醒等核心任务，也未按流程执行后续步骤。面对骑手质疑，虽进行了安抚但未有效挽留或按规则结束通话。表达质量因重复回复扣分。整体表现较差，需大幅改进。 |
| case_009 | 75.50 | 否 | 否 | 无 | 客服模型完成了合同生效通知、单量要求、连续天数要求等核心任务，知识引用准确，合规性良好，表达质量达标。但遗漏了安全提醒、挽留鼓励、报名机制解释和行为建议等关键步骤，导致任务完成度和流程执行度扣分。建议补充安全提醒话术，并在骑手表示愿意配送时给予鼓励。 |
| case_010 | 44.50 | 否 | 否 | 无 | 该case在任务完成度上仅完成3项核心任务，缺失挽留鼓励和安全提醒；流程执行度严重不足，仅执行3个步骤；知识准确性因未给出具体数值而扣分；异常处理能力得0分，因未正确应对骑手追问；表达质量因重复回复扣分。整体表现较差，需重点改进：1) 主动询问配送意愿并进行挽留/鼓励；2) 必须明确告知具体单量数值（X和Y）；3) 补充安全提醒；4) 避免重复回复。 |
| case_011 | 95.00 | 是 | 否 | process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism | 该case在任务完成度、知识准确性、合规性、异常处理能力和表达质量上均表现优秀，流程执行度因缺失解释报名排名机制和提供行为建议两个步骤扣5分，但整体表现良好，符合合格标准。 |
| case_012 | 77.50 | 否 | 否 | task_goal_consecutive_days_requirement, process_step_registration_mechanism_explanation, process_step_behavior_suggestion | 客服模型完成了大部分核心任务和流程步骤，但缺失连续天数要求、报名排名机制解释和行为建议。表达质量因重复回复被扣分。整体表现良好，但需补充缺失内容并避免重复。 |

## 5. 未覆盖项与证据

| case_id | missing_target | 缺失原因 |
|---|---|---|
| case_002 | process_step_registration_mechanism_explanation | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_002 | process_step_behavior_suggestion | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_002 | knowledge_accuracy_exit_mechanism | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_003 | task_goal_consecutive_days_requirement | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未进行安全提醒（步骤6） |
| case_003 | task_goal_safety_reminder | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未进行安全提醒（步骤6） |
| case_003 | process_step_registration_mechanism_explanation | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未进行安全提醒（步骤6） |
| case_003 | process_step_behavior_suggestion | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未进行安全提醒（步骤6） |
| case_003 | knowledge_accuracy_exit_mechanism | 未说明单日合同需连续Y天完成配送（连续天数要求）；未提醒骑手注意配送安全（安全提醒）；未进行安全提醒（步骤6） |
| case_007 | task_goal_retention_and_encouragement | 未对骑手进行挽留或鼓励（骑手未表达配送意愿，但站长也未主动询问或鼓励）；未提醒骑手注意配送安全；步骤3：询问配送意愿（未询问骑手是否可以开始配送） |
| case_007 | task_goal_safety_reminder | 未对骑手进行挽留或鼓励（骑手未表达配送意愿，但站长也未主动询问或鼓励）；未提醒骑手注意配送安全；步骤3：询问配送意愿（未询问骑手是否可以开始配送） |
| case_007 | process_step_willingness_inquiry | 未对骑手进行挽留或鼓励（骑手未表达配送意愿，但站长也未主动询问或鼓励）；未提醒骑手注意配送安全；步骤3：询问配送意愿（未询问骑手是否可以开始配送） |
| case_007 | process_step_registration_mechanism_explanation | 未对骑手进行挽留或鼓励（骑手未表达配送意愿，但站长也未主动询问或鼓励）；未提醒骑手注意配送安全；步骤3：询问配送意愿（未询问骑手是否可以开始配送） |
| case_007 | process_step_behavior_suggestion | 未对骑手进行挽留或鼓励（骑手未表达配送意愿，但站长也未主动询问或鼓励）；未提醒骑手注意配送安全；步骤3：询问配送意愿（未询问骑手是否可以开始配送） |
| case_008 | task_goal_daily_minimum_order_requirement | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | task_goal_consecutive_days_requirement | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | task_goal_retention_and_encouragement | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | task_goal_safety_reminder | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | process_step_registration_mechanism_explanation | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | process_step_behavior_suggestion | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_008 | knowledge_accuracy_additional_reward | 未说明单日合同每天至少X单；未说明多日合同每天至少Y单；未说明连续天数要求 |
| case_011 | process_step_registration_mechanism_explanation | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_011 | process_step_behavior_suggestion | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_011 | knowledge_accuracy_exit_mechanism | 未解释报名排名机制（步骤7）；未提供行为建议（步骤8） |
| case_012 | task_goal_consecutive_days_requirement | 未说明连续天数要求；未解释报名排名机制；未提供行为建议（减少拒单、取消、超时等） |
| case_012 | process_step_registration_mechanism_explanation | 未说明连续天数要求；未解释报名排名机制；未提供行为建议（减少拒单、取消、超时等） |
| case_012 | process_step_behavior_suggestion | 未说明连续天数要求；未解释报名排名机制；未提供行为建议（减少拒单、取消、超时等） |

## 6. 风险项

| case_id | risk_rule | severity | deduction | evidence |
|---|---|---|---:|---|
| case_003 | risk_miss_safety_reminder | medium | 5.00 | 第23轮both: 对话结束，站长未主动提醒骑手注意配送安全。 |
| case_004 | risk_miss_safety_reminder | medium | 5.00 | 第11轮agent: （对话结束，未出现安全提醒） |
| case_006 | risk_reply_repetition | low | 3.00 | 第4轮agent: 单日合同当天要完成X单，多日合同每天Y单，连续Y天。；第6轮agent: 单日X单，多日每天Y单，您考虑下能跑吗？；第8轮agent: 单日X单，多日每天Y单，具体看系统显示。；第10轮agent: 单日X单，多日每天Y单，具体数字您App里能看到。 |
| case_007 | risk_miss_safety_reminder | medium | 5.00 | 第7轮user: 行，知道了。没别的事我挂了。 |
| case_008 | risk_reply_repetition | low | 3.00 | 第14轮agent: 好的，我让同事确认后回电给您。；第16轮agent: 好的，我让同事确认后回电给您。 |
| case_009 | risk_miss_safety_reminder | medium | 5.00 | 第0轮agent: 您好，是李明吗？我是站长，今天飞毛腿合同已经签好了。 |
| case_010 | risk_miss_safety_reminder | medium | 5.00 | 第0轮agent: 您好，请问是张三吗？我是站长，今天飞毛腿合同已经签署了。 |
| case_010 | risk_reply_repetition | low | 3.00 | 第4轮agent: 单日合同当天要完成X单，多日每天Y单，连续Y天。；第6轮agent: 单日X单，多日每天Y单，连续Y天。；第8轮agent: 单日X单，多日每天Y单，连续Y天。具体数值以App显示为准。 |
| case_012 | risk_reply_repetition | low | 3.00 | 第16轮agent: 理解，那您先忙。注意安全，想跑了随时找我。；第18轮agent: 理解，那您先忙。注意安全，想跑了随时找我。；第20轮agent: 理解，那您先忙。注意安全，想跑了随时找我。 |

## 7. 改进建议

- 优先复查未通过的 6 个 case：case_006, case_007, case_008, case_009, case_010, case_012。
- 重点优化低得分维度：任务完成度, 流程执行度, 异常处理能力。
