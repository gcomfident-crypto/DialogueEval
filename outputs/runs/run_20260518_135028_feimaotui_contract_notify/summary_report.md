# 对话仿真汇总报告

- 总 case 数：4
- 成功完成对话数：1
- P0 场景通过率：25.0%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| feimaotui_contract_notify | 4 | 1 | 83.3% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_001 | flow_retention_encouragement, flow_ranking_mechanism_explanation |
| case_002 | flow_retention_encouragement |
| case_004 | flow_retention_encouragement |

## 风险标记列表

- 无

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| suspicion_drop | 2 |
| trust_increase | 2 |
| trust_rise | 2 |
| understanding_increase | 4 |
| user_requests_hangup | 3 |

## 需要补测的 case_id

- case_001
- case_002
- case_004

## 资产来源与模型配置

- run_id：run_20260518_135028_feimaotui_contract_notify
