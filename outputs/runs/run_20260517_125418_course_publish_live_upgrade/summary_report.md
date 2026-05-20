# 对话仿真汇总报告

- 总 case 数：2
- 成功完成对话数：0
- P0 场景通过率：0.0%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| course_publish_live_upgrade | 2 | 0 | 52.9% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_001 | upgrade_content_explanation, wecom_add_handling, web_console_display_handling, fee_setting_check, compliance_driving_handling |
| case_002 | publishing_method_inquiry, wecom_add_handling, third_party_system_guidance |

## 风险标记列表

| case_id | risk_flags |
|---|---|
| case_001 | cr_03:normal, cr_03:normal |

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| cost_concern_persists | 1 |
| cost_concern_rise | 2 |
| fraud_suspicion_rise | 1 |
| patience_drop | 2 |
| suspicion_rise | 2 |
| trust_drop | 2 |
| understanding_drop | 1 |
| urgency_rise | 2 |
| user_requests_brief | 1 |
| user_requests_hangup | 1 |

## 需要补测的 case_id

- case_001
- case_002

## 资产来源与模型配置

- run_id：run_20260517_125418_course_publish_live_upgrade
