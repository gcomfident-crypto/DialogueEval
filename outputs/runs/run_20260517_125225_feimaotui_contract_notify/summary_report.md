# 对话仿真汇总报告

- 总 case 数：2
- 成功完成对话数：0
- P0 场景通过率：0.0%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| feimaotui_contract_notify | 2 | 0 | 75.0% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_001 | knowledge_extra_reward, compliance_no_force_delivery |
| case_002 | task_delivery_willingness_confirmation, flow_consecutive_days_requirement |

## 风险标记列表

- 无

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| agent_mistake_corrected | 1 |
| patience_drop | 2 |
| patience_slight_drop | 1 |
| suspicion_decrease | 1 |
| suspicion_drop | 1 |
| trust_drop | 1 |
| trust_recovered | 2 |
| understanding_increase | 1 |
| understanding_rise | 1 |
| urgency_drop | 1 |
| urgency_rise | 2 |
| urgency_slight_rise | 1 |
| user_accepts_quit_procedure | 1 |
| user_requests_hangup | 2 |

## 需要补测的 case_id

- case_001
- case_002

## 资产来源与模型配置

- run_id：run_20260517_125225_feimaotui_contract_notify
