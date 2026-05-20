# 对话仿真汇总报告

- 总 case 数：10
- 成功完成对话数：2
- P0 场景通过率：28.6%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| feimaotui_contract_notify | 10 | 2 | 67.3% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_003 | daily_order_requirement, ranking_mechanism_explanation |
| case_004 | daily_order_requirement |
| case_005 | no_false_commitment |
| case_006 | no_unauthorized_waiver |
| case_007 | daily_order_requirement, continuous_delivery_requirement, ranking_mechanism_explanation |
| case_008 | daily_order_requirement, ranking_mechanism_explanation, peak_hours_online_requirement, scope_limitation_handling |
| case_009 | ranking_mechanism_explanation, peak_hours_online_requirement |
| case_010 | daily_order_requirement, ranking_mechanism_explanation, extra_reward_explanation, no_off_topic |

## 风险标记列表

| case_id | risk_flags |
|---|---|
| case_005 | cr_no_false_commitment:critical |

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| fraud_suspicion_rise | 3 |
| patience_drop | 7 |
| suspicion_decrease | 1 |
| suspicion_drop | 2 |
| suspicion_rise | 3 |
| trust_drop | 7 |
| trust_recovered | 3 |
| trust_rise | 1 |
| understanding_drop | 1 |
| understanding_increase | 4 |
| understanding_rise | 4 |
| urgency_rise | 3 |
| user_agrees_to_start | 1 |
| user_confirms_quit | 1 |
| user_refuse_delivery | 2 |
| user_refuses_today | 1 |
| user_requests_defer | 1 |
| user_requests_hangup | 7 |
| user_requests_simplify | 1 |

## 需要补测的 case_id

- case_003
- case_004
- case_005
- case_006
- case_007
- case_008
- case_009
- case_010

## 资产来源与模型配置

- run_id：run_20260519_121426_feimaotui_contract_notify
