# 对话仿真汇总报告

- 总 case 数：10
- 成功完成对话数：0
- P0 场景通过率：0.0%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| course_publish_live_upgrade | 10 | 0 | 48.0% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_001 | call_closure |
| case_002 | frontend_visibility_check, student_fee_check, wechat_work_add, call_closure |
| case_003 | frontend_visibility_check, wechat_work_add, call_closure |
| case_004 | awareness_confirmation, upgrade_content_delivery, frontend_visibility_check, student_fee_check, wechat_work_add, call_closure |
| case_005 | wechat_work_add, call_closure, driving_scenario_handling |
| case_006 | awareness_confirmation, upgrade_content_delivery, frontend_visibility_check, student_fee_check, wechat_work_add, call_closure |
| case_007 | upgrade_content_delivery, frontend_visibility_check, student_fee_check, wechat_work_add |
| case_008 | frontend_visibility_check, student_fee_check, wechat_work_add, call_closure |
| case_009 | student_fee_check, wechat_work_add, call_closure, student_fee_config_guidance |
| case_010 | student_fee_check, wechat_work_add, call_closure, third_party_config_guidance |

## 风险标记列表

| case_id | risk_flags |
|---|---|
| case_003 | cr_01:normal, cr_02:normal, cr_01:normal, cr_02:normal |
| case_005 | cr_01:critical, cr_01:critical, cr_01:critical, cr_01:critical, cr_01:critical, cr_01:critical, cr_01:critical, cr_01:critical |
| case_006 | cr_02:critical |

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| awareness_confirmed_unknown | 1 |
| cost_concern_rise | 1 |
| discount_hint_repeat | 1 |
| discount_request | 1 |
| discount_request_abandoned | 1 |
| discount_request_final | 1 |
| discount_request_repeat | 1 |
| fee_consistency_confirmed | 1 |
| fraud_suspicion_rise | 3 |
| frontend_visibility_confirmed | 1 |
| identity_confirmed | 3 |
| patience_drop | 10 |
| suspicion_drop | 4 |
| suspicion_rise | 5 |
| trust_drop | 8 |
| trust_rise | 1 |
| understanding_drop | 4 |
| understanding_rise | 8 |
| urgency_rise | 6 |
| user_asks_clarification | 1 |
| user_asks_setting_location | 1 |
| user_hints_end | 1 |
| user_impatient_unknown_info | 1 |
| user_questions_necessity | 1 |
| user_requests_hangup | 4 |
| user_requests_specific_cost | 1 |
| user_requests_step_by_step_guidance | 1 |
| wechat_work_add_confirmed | 1 |

## 需要补测的 case_id

- case_001
- case_002
- case_003
- case_004
- case_005
- case_006
- case_007
- case_008
- case_009
- case_010

## 资产来源与模型配置

- run_id：run_20260519_123045_course_publish_live_upgrade
