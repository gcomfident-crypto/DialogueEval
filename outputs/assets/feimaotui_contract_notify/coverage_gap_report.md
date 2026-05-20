# 覆盖缺口报告

- case 总数：10
- coverage label 覆盖率：13/13
- P0 label 覆盖率：7/7
- 覆盖矩阵行数：8

## Coverage Label 覆盖

| label | priority | case_count |
|---|---|---:|
| continuous_delivery_requirement | P0 | 10 |
| contract_effective_notification | P0 | 10 |
| daily_order_requirement | P0 | 10 |
| extra_reward_explanation | P1 | 1 |
| no_false_commitment | P0 | 2 |
| no_harassment | P0 | 2 |
| no_off_topic | P1 | 2 |
| no_unauthorized_waiver | P0 | 2 |
| peak_hours_online_requirement | P1 | 2 |
| persuasion_and_encouragement | P1 | 1 |
| quit_procedure_explanation | P1 | 1 |
| ranking_mechanism_explanation | P0 | 10 |
| scope_limitation_handling | P1 | 2 |

## 覆盖矩阵计划与实际

| matrix_id | priority | planned | generated |
|---|---|---:|---:|
| row_01 | P0 | 2 | 2 |
| row_02 | P0 | 2 | 2 |
| row_03 | P0 | 1 | 1 |
| row_04 | P0 | 1 | 1 |
| row_05 | P0 | 1 | 1 |
| row_06 | P1 | 1 | 1 |
| row_07 | P1 | 1 | 1 |
| row_08 | P1 | 1 | 1 |

## 用户模拟器质量评估

| 指标 | 公式 | 数值 | 说明 |
|---|---|---:|---|
| 指令点覆盖率 | 已覆盖 coverage label / 全部 coverage label | 13/13 (100.0%) | 衡量 case 是否覆盖任务模板中的必做项、知识项和禁忌项。 |
| P0 指令充足率 | P0 label 样本数达标 / 全部 P0 label | 7/7 (100.0%) | P0 默认至少需要 2 个样本，避免只出现一次但无法稳定评估。 |
| 分支覆盖率 | 已覆盖流程分支 / 全部流程分支 | 7/8 (87.5%) | 覆盖愿意、犹豫、拒绝、忙碌、质疑等业务流程路径。 |
| 关键分支充足率 | P0 流程分支样本数达标 / 全部 P0 流程分支 | 2/2 (100.0%) | 关键流程分支默认至少 2 个样本。 |
| 用户行为覆盖率 | 已覆盖用户行为 / 全部用户行为 | 10/10 (100.0%) | 衡量模拟用户是否覆盖配合、拒绝、怀疑、诱导违规等行为。 |
| 风险探针覆盖率 | 已覆盖风险探针 / 全部风险探针 | 8/8 (100.0%) | 衡量是否有 case 主动测试虚假承诺、强迫配送、错误解释等风险。 |
| 关键风险探针充足率 | P0 风险探针样本数达标 / 全部 P0 风险探针 | 3/3 (100.0%) | P0 风险探针默认至少 2 个样本。 |
| 用户画像多样性 | 画像使用率、画像属性差异、初始状态差异的均值 | 90.0% | 同时看 profile 是否被使用、画像字段是否有差异、case 初始心理状态是否有差异。 |
| 对话状态覆盖率 | 已覆盖动态状态路径 / 全部动态状态路径 | 6/8 (75.0%) | 覆盖信任上升、耐心下降、拒绝转愿意、突然挂断等动态路径。 |
| 关键状态路径充足率 | P0 动态状态路径样本数达标 / 全部 P0 动态状态路径 | 0/0 (0.0%) | P0 动态状态路径默认至少 2 个样本。 |
| 缺陷暴露设计率 | 已生成 case 的 forbidden_failures / 矩阵设计的 forbidden_failures | 24/24 (100.0%) | 说明测试用户是否覆盖了坏客服样例应暴露的失败模式；实际发现率由缺陷注入评测验证。 |

## 用户行为/流程/风险/动态状态覆盖

### 用户行为

| item_id | name | case_count |
|---|---|---:|
| ub_cooperative | 配合确认 | 3 |
| ub_refuse | 明确拒绝 | 3 |
| ub_hesitate | 犹豫不决 | 1 |
| ub_busy | 忙碌状态 | 1 |
| ub_repeat_confirm | 反复确认 | 1 |
| ub_off_topic | 题外话 | 1 |
| ub_suspicious_fraud | 怀疑诈骗 | 1 |
| ub_impatient | 情绪不耐烦 | 1 |
| ub_induce_violation | 诱导违规 | 1 |
| ub_complain_ranking | 抱怨排名 | 1 |

### 流程分支

| item_id | name | case_count |
|---|---|---:|
| fb_accept_delivery | 骑手接受配送 | 2 |
| fb_refuse_delivery | 骑手拒绝配送 | 3 |
| fb_hesitate_uncertain | 骑手犹豫或不确定 | 1 |
| fb_ask_about_contract | 骑手询问合同细节 | 1 |
| fb_ask_about_ranking | 骑手询问排名机制 | 1 |
| fb_ask_about_quit | 骑手询问退出流程 | 1 |
| fb_ask_out_of_scope | 骑手提出超出职责范围的问题 | 1 |
| fb_user_hangup | 骑手突然挂断 | 0 |

### 风险探针

| item_id | name | case_count |
|---|---|---:|
| rp_false_commitment | 虚假承诺 | 7 |
| rp_unauthorized_waiver | 擅自免除要求 | 4 |
| rp_harassment | 威胁辱骂 | 7 |
| rp_off_topic | 讨论无关话题 | 1 |
| rp_missing_peak_hours | 未提醒高峰期上线 | 1 |
| rp_missing_quit_procedure | 未正确说明退出流程 | 1 |
| rp_missing_extra_reward | 未正确说明额外奖励 | 1 |
| rp_missing_scope_handling | 未使用标准话术处理超出职责范围问题 | 1 |

### 动态状态路径

| item_id | name | case_count |
|---|---|---:|
| dsp_suspicion_decrease | 怀疑下降 | 1 |
| dsp_patience_decrease | 耐心下降 | 1 |
| dsp_understanding_increase | 理解提升 | 4 |
| dsp_sudden_hangup | 突然要挂断 | 1 |
| dsp_refuse_to_accept | 拒绝转为接受 | 2 |
| dsp_accept_to_refuse | 接受转为拒绝 | 0 |
| dsp_emotional_escalation | 情绪升级 | 2 |
| dsp_emotional_deescalation | 情绪缓和 | 0 |


## 需要补测

- 暂无 coverage label 缺口。

- 流程分支样本不足：fb_user_hangup 当前 0，建议至少 1
- 动态状态路径样本不足：dsp_accept_to_refuse 当前 0，建议至少 1
- 动态状态路径样本不足：dsp_emotional_deescalation 当前 0，建议至少 1
