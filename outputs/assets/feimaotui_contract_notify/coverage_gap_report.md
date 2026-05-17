# 覆盖缺口报告

- case 总数：20
- coverage label 覆盖率：12/12
- P0 label 覆盖率：9/9
- 覆盖矩阵行数：16

## Coverage Label 覆盖

| label | priority | case_count |
|---|---|---:|
| compliance_no_encourage_violation | P0 | 4 |
| compliance_no_false_commitment | P0 | 4 |
| compliance_no_unauthorized_intervention | P0 | 4 |
| expression_quality_natural_tone | P1 | 3 |
| flow_explain_contract_type_daily | P0 | 15 |
| flow_explain_contract_type_multi | P0 | 13 |
| flow_explain_ranking_mechanism | P0 | 11 |
| flow_retain_reluctant_rider | P0 | 7 |
| knowledge_extra_reward | P1 | 2 |
| knowledge_quit_procedure | P1 | 2 |
| task_confirm_delivery_willingness | P0 | 20 |
| task_confirm_identity_and_contract | P0 | 20 |

## 覆盖矩阵计划与实际

| matrix_id | priority | planned | generated |
|---|---|---:|---:|
| row_01 | P0 | 2 | 2 |
| row_02 | P0 | 2 | 2 |
| row_03 | P0 | 1 | 1 |
| row_04 | P0 | 2 | 2 |
| row_05 | P0 | 2 | 2 |
| row_06 | P0 | 1 | 1 |
| row_07 | P0 | 1 | 1 |
| row_08 | P1 | 1 | 1 |
| row_09 | P1 | 1 | 1 |
| row_10 | P1 | 1 | 1 |
| row_11 | P1 | 1 | 1 |
| row_12 | P1 | 1 | 1 |
| row_13 | P1 | 1 | 1 |
| row_14 | P1 | 1 | 1 |
| row_15 | P1 | 1 | 1 |
| row_16 | P1 | 1 | 1 |

## 用户行为/流程/风险/动态状态覆盖

### 用户行为

| item_id | name | case_count |
|---|---|---:|
| ub_cooperative | 配合确认 | 3 |
| ub_refuse_delivery | 拒绝配送 | 3 |
| ub_hesitant | 犹豫不决 | 1 |
| ub_busy | 忙碌状态 | 1 |
| ub_repeat_confirm | 反复确认 | 1 |
| ub_off_topic | 题外话 | 1 |
| ub_suspect_fraud | 怀疑诈骗 | 3 |
| ub_impatient | 情绪不耐烦 | 2 |
| ub_induce_violation | 诱导违规 | 2 |
| ub_ask_quit | 询问退出流程 | 1 |
| ub_ask_reward | 询问奖励 | 1 |
| ub_ask_out_of_scope | 提出超出职责范围的问题 | 1 |

### 流程分支

| item_id | name | case_count |
|---|---|---:|
| flow_explain_contract_type_daily | 说明单日合同要求 | 14 |
| flow_explain_contract_type_multi | 说明多日合同要求 | 13 |
| flow_retain_reluctant_rider | 挽留不想配送的骑手 | 6 |
| flow_explain_ranking_mechanism | 解释飞毛腿排名机制 | 9 |
| flow_handle_quit_request | 处理退出飞毛腿请求 | 1 |
| flow_handle_reward_inquiry | 处理奖励咨询 | 1 |
| flow_handle_out_of_scope | 处理超出职责范围的问题 | 1 |
| flow_end_call_positive | 积极结束通话 | 1 |
| flow_end_call_negative | 消极结束通话 | 2 |

### 风险探针

| item_id | name | case_count |
|---|---|---:|
| risk_false_commitment | 虚假承诺风险 | 8 |
| risk_unauthorized_intervention | 声称可干预排名风险 | 6 |
| risk_encourage_violation | 鼓励违规风险 | 2 |
| risk_abusive_language | 侮辱性语言风险 | 4 |
| risk_incomplete_contract_info | 合同信息不完整风险 | 4 |
| risk_no_retention | 未挽留风险 | 5 |
| risk_repeated_response | 重复回复风险 | 3 |
| risk_excessive_length | 回复过长风险 | 3 |
| risk_scope_not_handled | 未处理超范围问题风险 | 2 |

### 动态状态路径

| item_id | name | case_count |
|---|---|---:|
| dsp_suspicion_decrease | 怀疑下降 | 3 |
| dsp_patience_decrease | 耐心下降 | 1 |
| dsp_understanding_increase | 理解提升 | 3 |
| dsp_sudden_hangup | 突然要挂断 | 2 |
| dsp_refuse_to_accept | 拒绝转为接受 | 3 |
| dsp_accept_to_refuse | 接受转为拒绝 | 1 |
| dsp_emotional_escalation | 情绪升级 | 1 |
| dsp_emotional_deescalation | 情绪缓和 | 1 |


## 需要补测

- 暂无 coverage label 缺口。
