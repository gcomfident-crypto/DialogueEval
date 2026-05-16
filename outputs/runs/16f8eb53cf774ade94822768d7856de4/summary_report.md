# 对话仿真汇总报告

- 总 case 数：12
- 成功完成对话数：6
- P0 场景通过率：50.0%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| meituan_feimaotui_contract_notification | 12 | 6 | 85.3% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_002 | process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism |
| case_003 | task_goal_consecutive_days_requirement, task_goal_safety_reminder, process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism |
| case_007 | task_goal_retention_and_encouragement, task_goal_safety_reminder, process_step_willingness_inquiry, process_step_registration_mechanism_explanation, process_step_behavior_suggestion |
| case_008 | task_goal_daily_minimum_order_requirement, task_goal_consecutive_days_requirement, task_goal_retention_and_encouragement, task_goal_safety_reminder, process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_additional_reward |
| case_011 | process_step_registration_mechanism_explanation, process_step_behavior_suggestion, knowledge_accuracy_exit_mechanism |
| case_012 | task_goal_consecutive_days_requirement, process_step_registration_mechanism_explanation, process_step_behavior_suggestion |

## 风险标记列表

| case_id | risk_flags |
|---|---|
| case_006 | c5:normal |
| case_012 | c5:normal, c5:normal |

## 需要补测的 case_id

- case_002
- case_003
- case_007
- case_008
- case_011
- case_012

## 资产来源与模型配置

- run_id：16f8eb53cf774ade94822768d7856de4
