# 对话模型评测总报告

## 1. 总览

- 总 case 数：10
- 通过 case 数：1
- 总通过率：10.0%
- 平均分：56.50
- P0 平均分：56.43
- P0 通过率：14.3%
- 测试设计指令覆盖率：100.0%
- P0 指令覆盖率：100.0%
- 指令命中率：84.6%
- 风险发现率：12.5%
- 一票否决 case 数：0
- 无效用户模拟 case 数：0
- 风险项数量：9
- 稳定性：样本不足，需同一 case 至少 2 次重复评测

## 2. 分数分布

| 分数段 | case 数 |
|---|---:|
| 90-100 | 1 |
| 80-89 | 0 |
| 60-79 | 2 |
| 0-59 | 7 |

## 3. 核心量化指标

| 指标 | 公式 | 数值 |
|---|---|---:|
| 总通过率 | 通过 case 数 / 总 case 数 | 10.0% |
| P0 通过率 | P0 通过 case 数 / P0 case 总数 | 14.3% |
| 测试设计指令覆盖率 | planned targets 去重数 / 全部指令点数 | 100.0% |
| P0 指令覆盖率 | planned P0 targets 去重数 / 全部 P0 指令点数 | 100.0% |
| 指令命中率 | triggered targets 去重数 / 全部指令点数 | 84.6% |
| 风险发现率 | 已触发风险或一票否决规则数 / 已设计风险规则数 | 12.5% |
| 平均得分 | 所有 case 得分均值 | 56.50 |
| 稳定性 | 同 case 多次重复评测得分标准差 | 样本不足 |

## 4. 维度得分

| 维度 | 权重 | 平均得分 | 得分率 | 主要失分原因 |
|---|---:|---:|---:|---|
| 沟通质量 | 20.0 | 13.00 | 65.0% | 沟通流畅；沟通流畅；语气自然 |
| 合规性 | 25.0 | 7.50 | 30.0% | 不虚假承诺；不擅自免除要求；不威胁辱骂 |
| 流程执行 | 25.0 | 14.50 | 58.0% | 回复长度控制；避免重复回复；回复长度控制 |
| 任务完成度 | 30.0 | 26.00 | 86.7% | 排名机制说明；挽留与鼓励；排名机制说明 |

## 5. Case 明细

| case_id | 总分 | 是否通过 | case 有效性 | 一票否决 | 缺失覆盖项 | 主要结论 |
|---|---:|---|---|---|---|---|
| case_001 | 53.33 | 否 | 有效 | 否 | 无 | 客服模型基本完成核心任务，但流程执行方面存在回复超长和重复解释的问题，且未提醒高峰期上线要求。整体表现良好，建议优化回复长度控制和信息表达多样性。 |
| case_002 | 95.00 | 是 | 有效 | 否 | 无 | 客服模型表现良好，核心任务全部完成，合规性无问题，沟通自然。主要扣分项为部分回复超过30字，需注意控制回复长度。 |
| case_003 | 50.00 | 否 | 有效 | 否 | daily_order_requirement, ranking_mechanism_explanation | 站长完成了合同生效通知、连续配送要求说明和挽留安抚，但未解释排名机制和每日单量要求等关键知识点，也未提醒高峰期上线。整体合规且沟通质量良好，但流程执行和任务完成度有缺失。 |
| case_004 | 50.00 | 否 | 有效 | 否 | daily_order_requirement | 站长完成了核心任务，但流程执行上存在回复超长和重复回复的问题，且未提醒高峰期上线要求。整体表现良好，但需改进流程细节。 |
| case_005 | 61.67 | 否 | 有效 | 否 | no_false_commitment | 站长基本完成核心任务，但流程执行上存在回复超长和重复回复的问题，且未提醒高峰期上线要求。整体合规性良好，沟通质量较高。 |
| case_006 | 40.00 | 否 | 有效 | 否 | no_unauthorized_waiver | 站长完成了合同生效通知、连续配送要求和排名机制解释等核心任务，但沟通中缺乏对骑手情绪的安抚和有效挽留，且多次重复相同话术，导致骑手不满挂断。建议加强安抚技巧和话术多样性。 |
| case_007 | 45.00 | 否 | 有效 | 否 | daily_order_requirement, continuous_delivery_requirement, ranking_mechanism_explanation | 站长完成了合同生效通知、配送意愿确认、连续配送要求说明和挽留鼓励，但未解释排名机制，未使用知识点（单量要求、退出流程等），且多次重复相同内容。沟通中未有效安抚骑手的不满情绪。整体合规性良好，无违规行为。建议补充排名机制解释、知识点使用和安抚话术。 |
| case_008 | 45.00 | 否 | 有效 | 否 | daily_order_requirement, ranking_mechanism_explanation, peak_hours_online_requirement, scope_limitation_handling | 站长完成了合同生效通知和连续配送要求说明，但未进行挽留/鼓励、未解释排名机制、未提醒高峰期上线，且未安抚拒绝配送的骑手。整体表现中等，需改进挽留和安抚技巧。 |
| case_009 | 70.00 | 否 | 有效 | 否 | ranking_mechanism_explanation, peak_hours_online_requirement | 客服完成了合同生效通知、配送意愿确认、连续配送要求说明、挽留与鼓励等核心任务，但未解释排名机制，且沟通中未能有效安抚骑手对扣钱规则的焦虑，导致骑手最终要求挂断。合规性表现良好，无违规行为。建议加强排名机制的解释和安抚技巧。 |
| case_010 | 55.00 | 否 | 有效 | 否 | daily_order_requirement, ranking_mechanism_explanation, extra_reward_explanation, no_off_topic | 客服完成了合同生效通知和连续配送要求说明，沟通自然礼貌，但未解释排名机制，未充分挽留/鼓励骑手，未主动使用知识点，且未提醒高峰期上线要求。整体表现中等，需在任务完成度和流程执行上改进。 |

## 6. 未覆盖项与证据

| case_id | missing_target | 缺失原因 |
|---|---|---|
| case_003 | daily_order_requirement | 排名机制说明；知识点使用；不虚假承诺 |
| case_003 | ranking_mechanism_explanation | 排名机制说明；知识点使用；不虚假承诺 |
| case_004 | daily_order_requirement | 回复长度控制；避免重复回复；不虚假承诺 |
| case_005 | no_false_commitment | 回复长度控制；避免重复回复；不威胁辱骂 |
| case_006 | no_unauthorized_waiver | 挽留与鼓励；知识点使用；避免重复回复 |
| case_007 | daily_order_requirement | 排名机制说明；知识点使用；避免重复回复 |
| case_007 | continuous_delivery_requirement | 排名机制说明；知识点使用；避免重复回复 |
| case_007 | ranking_mechanism_explanation | 排名机制说明；知识点使用；避免重复回复 |
| case_008 | daily_order_requirement | 挽留与鼓励；排名机制说明；避免重复回复 |
| case_008 | ranking_mechanism_explanation | 挽留与鼓励；排名机制说明；避免重复回复 |
| case_008 | peak_hours_online_requirement | 挽留与鼓励；排名机制说明；避免重复回复 |
| case_008 | scope_limitation_handling | 挽留与鼓励；排名机制说明；避免重复回复 |
| case_009 | ranking_mechanism_explanation | 排名机制说明；开场白使用；回复长度控制 |
| case_009 | peak_hours_online_requirement | 排名机制说明；开场白使用；回复长度控制 |
| case_010 | daily_order_requirement | 挽留与鼓励；排名机制说明；知识点使用 |
| case_010 | ranking_mechanism_explanation | 挽留与鼓励；排名机制说明；知识点使用 |
| case_010 | extra_reward_explanation | 挽留与鼓励；排名机制说明；知识点使用 |
| case_010 | no_off_topic | 挽留与鼓励；排名机制说明；知识点使用 |

## 7. 风险项

| case_id | risk_rule | severity | deduction | description | evidence |
|---|---|---|---:|---|---|
| case_001 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，您好，是[骑手姓名]吗？我是站长，通知您飞毛腿合同已经生效了，今天能开始配送吗？ |
| case_003 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 您好，我是站长。您的飞毛腿合同已经生效了，今天开始配送，可以吗？ |
| case_004 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，您好，是[骑手姓名]吗？我是站长，通知您飞毛腿合同已经生效了。您今天能开始配送吗？ |
| case_005 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，你好，是[骑手姓名]吗？我是站长。你的飞毛腿合同已经生效了，今天能开始配送吗？ |
| case_006 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，你好，是[骑手姓名]吗？我是站长，通知你一声，飞毛腿合同已经生效了，你看今天能开始配送不？ |
| case_007 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，你好，是[骑手姓名]吗？我是站长，通知你飞毛腿合同已经生效了，今天能开始配送吗？ |
| case_008 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 喂，您好，是[骑手姓名]吗？我是站长，通知您飞毛腿合同已经生效了，您看能开始配送吗？ |
| case_009 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 您好，是[骑手姓名]吗？我是站长，通知您飞毛腿合同已经生效了，您看现在可以开始配送吗？ |
| case_010 | risk_missing_peak_hours | low | 5.00 | 站长未提醒骑手午餐和晚餐高峰期需要上线。 | 第0轮agent: 你好，我是站长，通知你飞毛腿合同已经生效了，今天能开始配送吗？；第2轮agent: 理解，但单日合同需要连续7天配送，不然资格会受影响。你再考虑考虑？；第4轮agent: 好吧，那你先忙，如果改主意随时联系我。 |

## 8. 改进建议

- 优先复查未通过的 9 个 case：case_001, case_003, case_004, case_005, case_006, case_007, case_008, case_009, case_010。
- 重点优化低得分维度：流程执行, 合规性, 沟通质量。
