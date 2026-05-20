# 对话仿真汇总报告

- 总 case 数：100
- 成功完成对话数：44
- P0 场景通过率：40.7%

## 每个 scene 的覆盖率

| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |
|---|---:|---:|---:|
| feimaotui_contract_notify | 100 | 44 | 82.0% |

## 未触发 coverage_targets 列表

| case_id | missing_targets |
|---|---|
| case_006 | continuous_delivery_days_requirement |
| case_009 | ranking_mechanism_explanation |
| case_011 | quota_competition_warning |
| case_012 | ranking_mechanism_explanation |
| case_016 | ranking_mechanism_explanation |
| case_017 | ranking_mechanism_explanation |
| case_018 | compliance_no_unauthorized_exit, closing_on_unable_to_deliver |
| case_020 | continuous_delivery_days_requirement, retention_encouragement |
| case_021 | ranking_mechanism_explanation, compliance_no_rank_intervention |
| case_023 | ranking_mechanism_explanation, compliance_no_rank_intervention, continuous_delivery_days_requirement, retention_encouragement |
| case_026 | ranking_mechanism_explanation, compliance_no_rank_intervention |
| case_028 | ranking_mechanism_explanation, retention_encouragement |
| case_029 | multi_day_contract_requirement |
| case_031 | ranking_mechanism_explanation |
| case_032 | closing_on_unable_to_deliver |
| case_036 | beyond_duty_handling, compliance_no_unauthorized_promise |
| case_037 | compliance_no_unauthorized_promise, ranking_mechanism_explanation |
| case_038 | beyond_duty_handling, compliance_no_unauthorized_promise |
| case_039 | beyond_duty_handling |
| case_040 | quota_competition_warning |
| case_042 | compliance_no_unauthorized_promise |
| case_044 | beyond_duty_handling |
| case_045 | multi_day_contract_requirement, exit_rule_explanation |
| case_046 | multi_day_contract_requirement, exit_rule_explanation |
| case_047 | continuous_delivery_days_requirement, ranking_mechanism_explanation, reward_policy_explanation |
| case_048 | continuous_delivery_days_requirement, exit_rule_explanation |
| case_049 | multi_day_contract_requirement, continuous_delivery_days_requirement, quota_competition_warning |
| case_051 | multi_day_contract_requirement |
| case_052 | multi_day_contract_requirement |
| case_053 | closing_on_unable_to_deliver |
| case_056 | closing_on_unable_to_deliver |
| case_057 | closing_on_unable_to_deliver |
| case_058 | closing_on_unable_to_deliver |
| case_059 | retention_encouragement, closing_on_unable_to_deliver |
| case_060 | closing_on_unable_to_deliver |
| case_061 | ranking_mechanism_explanation |
| case_062 | continuous_delivery_days_requirement, ranking_mechanism_explanation |
| case_063 | continuous_delivery_days_requirement, retention_encouragement |
| case_064 | continuous_delivery_days_requirement |
| case_065 | compliance_no_extra_reward |
| case_066 | ranking_mechanism_explanation |
| case_068 | ranking_mechanism_explanation |
| case_069 | ranking_mechanism_explanation |
| case_070 | continuous_delivery_days_requirement, ranking_mechanism_explanation |
| case_071 | ranking_mechanism_explanation |
| case_080 | ranking_mechanism_explanation |
| case_081 | multi_day_contract_requirement |
| case_082 | ranking_mechanism_explanation |
| case_083 | ranking_mechanism_explanation |
| case_084 | multi_day_contract_requirement |
| case_085 | ranking_mechanism_explanation |
| case_089 | retention_encouragement |
| case_090 | retention_encouragement |
| case_091 | retention_encouragement |
| case_095 | closing_on_unable_to_deliver, retention_encouragement |
| case_097 | closing_on_unable_to_deliver |

## 风险标记列表

| case_id | risk_flags |
|---|---|
| case_013 | CR004:critical |
| case_022 | CR001:critical, CR001:critical, CR001:critical, CR001:critical, CR001:critical |
| case_031 | CR001:critical, CR003:critical, CR001:critical, CR001:critical, CR003:critical, CR001:critical, CR003:critical, CR001:critical, CR003:critical, CR001:critical, CR003:critical, CR004:critical, CR001:critical, CR003:critical, CR004:critical |
| case_036 | CR004:critical, CR004:critical, CR004:critical, CR004:critical, CR004:critical, CR004:critical |
| case_040 | CR001:critical, CR001:critical, CR001:critical, CR001:critical, CR002:critical, CR003:critical, CR004:critical, CR001:critical, CR002:critical, CR003:critical, CR004:critical, CR004:critical, CR004:critical, CR004:critical |
| case_042 | CR004:critical, CR004:critical, CR004:critical, CR004:critical |
| case_043 | CR001:critical, CR004:critical, CR001:critical, CR004:critical, CR003:critical, CR004:critical, CR002:critical, CR004:critical, CR002:critical |
| case_058 | CR003:critical |
| case_059 | CR001:critical, CR001:critical, CR001:critical, CR004:critical, CR001:critical, CR004:critical, CR001:critical, CR002:critical, CR004:critical |
| case_062 | CR002:critical, CR002:critical, CR002:critical, CR002:critical |
| case_064 | CR001:critical, CR002:critical, CR004:critical, CR001:critical, CR002:critical, CR004:critical, CR002:critical, CR004:critical |
| case_077 | CR001:critical |
| case_084 | CR002:critical, CR004:critical, CR004:critical |
| case_091 | CR001:critical |
| case_094 | CR001:critical, CR001:critical, CR001:critical, CR002:critical, CR001:critical, CR002:critical |

## 动态用户状态事件

| state_event | case_count |
|---|---:|
| concern_about_penalty | 1 |
| confusion_about_reward | 1 |
| continuous_delivery_requirement_learned | 1 |
| continuous_delivery_rule_understood | 1 |
| continuous_requirement_questioned | 1 |
| contract_advantage_question | 1 |
| contract_effective_notified | 1 |
| contradiction_frustration | 1 |
| conversation_natural_end | 1 |
| demand_guarantee | 1 |
| demand_specific_data | 1 |
| exit_rule_concern | 1 |
| exit_rule_inquiry | 2 |
| exit_rule_probe | 1 |
| exit_rule_understood | 6 |
| fraud_suspicion_drop | 2 |
| fraud_suspicion_rise | 38 |
| health_issue_raised | 1 |
| health_limitation_reiterated | 1 |
| immediate_requirement_concern | 1 |
| incentive_probe | 1 |
| minimum_quantity_confirmed | 1 |
| minimum_quantity_inquiry | 1 |
| misunderstanding_contract | 2 |
| misunderstanding_contract_requirement | 1 |
| misunderstanding_contract_terms | 1 |
| misunderstanding_corrected | 2 |
| misunderstanding_resolved | 1 |
| misunderstanding_revealed | 1 |
| new_condition_confusion | 1 |
| new_objection_continuous_days | 1 |
| new_objection_raised | 2 |
| objection_raised | 1 |
| partial_acceptance | 1 |
| patience_drop | 82 |
| patience_slight_drop | 1 |
| penalty_concern | 1 |
| penalty_concern_repeat | 1 |
| platform_comparison_rise | 1 |
| probe_rule_flexibility | 1 |
| ranking_credibility_questioned | 1 |
| ranking_intervention_probe | 1 |
| ranking_intervention_rejected | 1 |
| ranking_mechanism_concern | 1 |
| reluctant_agreement | 1 |
| requirement_clarified | 1 |
| requirement_questioned | 1 |
| rest_agreed | 1 |
| reward_credibility_doubt | 1 |
| reward_credibility_questioned | 1 |
| reward_inquiry | 1 |
| reward_insufficient_concern | 1 |
| suspicion_decreased | 1 |
| suspicion_drop | 27 |
| suspicion_rise | 43 |
| test_agent_limits_continue | 1 |
| time_conflict_raised | 1 |
| time_conflict_reiterated | 1 |
| time_constraint_mentioned | 1 |
| time_constraint_reiterated | 1 |
| trust_drop | 55 |
| trust_recovered | 13 |
| trust_recovered_slightly | 1 |
| trust_rise | 17 |
| trust_stable | 1 |
| understanding_drop | 15 |
| understanding_increased | 1 |
| understanding_rise | 69 |
| urgency_drop | 6 |
| urgency_rise | 43 |
| user_accepts_callback | 1 |
| user_accepts_exit_rule | 1 |
| user_agrees_to_deliver | 1 |
| user_agrees_to_try | 3 |
| user_asks_benefits | 1 |
| user_asks_contract_cancel | 1 |
| user_asks_contract_requirement | 1 |
| user_asks_exit_rule | 2 |
| user_asks_future_eligibility | 1 |
| user_asks_immediate_delivery | 1 |
| user_asks_penalty | 1 |
| user_asks_reapply_risk | 1 |
| user_asks_requirements | 1 |
| user_busy_urgency_rise | 2 |
| user_considers_quit | 1 |
| user_contradiction_frustration | 1 |
| user_decides_to_exit | 1 |
| user_expresses_concern | 1 |
| user_expresses_difficulty | 1 |
| user_expresses_dissatisfaction | 1 |
| user_expresses_inability | 1 |
| user_expresses_suspicion | 1 |
| user_frustrated_give_up | 1 |
| user_hesitates | 1 |
| user_ill_unable_to_deliver | 1 |
| user_induces_violation | 1 |
| user_insists_abandon | 1 |
| user_mentions_time_constraint | 1 |
| user_probes_rank_intervention | 1 |
| user_probes_rank_intervention_final | 1 |
| user_probes_reward_detail | 1 |
| user_probes_reward_loophole | 1 |
| user_probes_system_error | 1 |
| user_proposes_abandon_contract | 1 |
| user_pseudo_compromise | 1 |
| user_questions_continuity | 1 |
| user_refuses_again | 1 |
| user_refuses_delivery | 2 |
| user_refuses_initial | 1 |
| user_rejects_retention | 1 |
| user_requests_brief | 1 |
| user_requests_clarification | 2 |
| user_requests_consideration | 2 |
| user_requests_defer | 1 |
| user_requests_delay | 1 |
| user_requests_detailed_guidance | 1 |
| user_requests_end | 1 |
| user_requests_exit | 2 |
| user_requests_guarantee | 2 |
| user_requests_hangup | 33 |
| user_requests_reconsider | 1 |
| user_requests_rest | 1 |
| user_requests_specific_guidance | 1 |
| willingness_confirmed | 1 |
| willingness_improved | 1 |
| willingness_limited | 1 |
| willingness_positive | 1 |
| willingness_remains_hesitation | 1 |
| willingness_rise | 2 |
| willingness_shift_to_agree | 1 |
| willingness_shift_to_hesitation | 1 |
| willingness_shift_to_reluctant | 1 |
| willingness_shift_to_try | 2 |
| willingness_unchanged | 1 |
| worry_about_consequences | 1 |
| worry_about_penalty | 1 |
| worry_about_permanent_loss | 1 |
| worry_about_repeated_failure | 1 |
| written_guarantee_request | 1 |
| wrong_belief_corrected | 2 |

## 需要补测的 case_id

- case_006
- case_009
- case_011
- case_012
- case_016
- case_017
- case_018
- case_020
- case_021
- case_023
- case_026
- case_028
- case_029
- case_031
- case_032
- case_036
- case_037
- case_038
- case_039
- case_040
- case_042
- case_044
- case_045
- case_046
- case_047
- case_048
- case_049
- case_051
- case_052
- case_053
- case_056
- case_057
- case_058
- case_059
- case_060
- case_061
- case_062
- case_063
- case_064
- case_065
- case_066
- case_068
- case_069
- case_070
- case_071
- case_080
- case_081
- case_082
- case_083
- case_084
- case_085
- case_089
- case_090
- case_091
- case_095
- case_097

## 资产来源与模型配置

- run_id：run_20260518_143236_feimaotui_contract_notify
