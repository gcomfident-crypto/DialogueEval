# 对话模型评测总报告

## 1. 总览

- 总 case 数：2
- 通过 case 数：0
- 通过率：0.0%
- 平均分：51.00
- P0 平均分：51.00
- P0 通过率：0.0%
- 一票否决 case 数：0
- 风险项数量：7

## 2. 分数分布

| 分数段 | case 数 |
|---|---:|
| 90-100 | 0 |
| 80-89 | 0 |
| 60-79 | 0 |
| 0-59 | 2 |

## 3. 维度得分

| 维度 | 权重 | 平均得分 | 得分率 | 主要失分原因 |
|---|---:|---:|---:|---|
| 合规性 | 20.0 | 20.00 | 100.0% | 无 |
| 表达简洁性 | 15.0 | 13.50 | 90.0% | 无 |
| 知识准确性 | 10.0 | 10.00 | 100.0% | 无 |
| 流程执行 | 25.0 | 10.00 | 40.0% | 未执行升级内容说明步骤；未执行显示处理步骤；未执行费用检查步骤 |
| 任务完成度 | 30.0 | 7.50 | 25.0% | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |

## 4. Case 明细

| case_id | 总分 | 是否通过 | 一票否决 | 缺失覆盖项 | 主要结论 |
|---|---:|---|---|---|---|
| case_001 | 47.00 | 否 | 否 | upgrade_content_explanation, wecom_add_handling, web_console_display_handling, fee_setting_check, compliance_driving_handling | 客服在身份确认和知情确认步骤执行正确，但未能有效传达升级核心内容（发布页分开显示选项），且未处理前端可见性、费用检查、企业微信添加等关键步骤。面对客户对具体费用的反复追问，客服未能提供明确数字，导致客户耐心耗尽主动挂断，任务未完成。表达简洁性略有不足，但合规性良好。 |
| case_002 | 55.00 | 否 | 否 | publishing_method_inquiry, wecom_add_handling, third_party_system_guidance | 客服在身份确认、知情确认、升级内容说明、合规性和表达简洁性方面表现良好，但任务完成度和流程执行严重不足：客户未理解升级内容，仍认为低延迟直播是推销收费；缺失发布方式询问、显示处理、费用检查、企业微信添加和结束通话等多个关键步骤。风险扣分项为未询问发布方式和未处理企业微信添加。 |

## 5. 未覆盖项与证据

| case_id | missing_target | 缺失原因 |
|---|---|---|
| case_001 | upgrade_content_explanation | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |
| case_001 | wecom_add_handling | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |
| case_001 | web_console_display_handling | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |
| case_001 | fee_setting_check | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |
| case_001 | compliance_driving_handling | 客户未明确表示理解升级内容；未确认前端可见性；未完成企业微信添加 |
| case_002 | publishing_method_inquiry | 客户未确认前端可见性；客户未完成企业微信添加；客户仍有未解答疑问（未来收费问题） |
| case_002 | wecom_add_handling | 客户未确认前端可见性；客户未完成企业微信添加；客户仍有未解答疑问（未来收费问题） |
| case_002 | third_party_system_guidance | 客户未确认前端可见性；客户未完成企业微信添加；客户仍有未解答疑问（未来收费问题） |

## 6. 风险项

| case_id | risk_rule | severity | deduction | evidence |
|---|---|---|---:|---|
| case_001 | risk_upgrade_not_explained | high | 5.00 | 第4轮agent: 之前前端没开放，后台临时开的，保障同步。低延迟费用略高，但效果好。 |
| case_001 | risk_wecom_not_handled | high | 5.00 | 第13轮user: 你老是说明细明细，我现在就要知道大概数字，不然这电话我挂了啊。 |
| case_002 | risk_identity_not_confirmed | high | 0.00 | 第0轮agent: 您好，请问您是贵培训机构/校区的负责人吗？ |
| case_002 | risk_awareness_not_checked | high | 0.00 | 第2轮agent: 您之前选的标准直播，后台其实已为您走低延迟线路，您知道吗？ |
| case_002 | risk_upgrade_not_explained | high | 0.00 | 第6轮agent: 之后发布页会分开显示两个选项。 |
| case_002 | risk_publishing_method_not_asked | high | 5.00 | 第9轮user: 那不就等于以后选这个功能就要加钱？你这说来说去不还是要推销吗？ |
| case_002 | risk_wecom_not_handled | high | 5.00 | 第9轮user: 那不就等于以后选这个功能就要加钱？你这说来说去不还是要推销吗？ |

## 7. 改进建议

- 优先复查未通过的 2 个 case：case_001, case_002。
- 重点优化低得分维度：任务完成度, 流程执行。
