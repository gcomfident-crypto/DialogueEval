# 对话模型评测总报告

## 1. 总览

- 总 case 数：1
- 通过 case 数：0
- 通过率：0.0%
- 平均分：65.00
- P0 平均分：65.00
- P0 通过率：0.0%
- 一票否决 case 数：0
- 风险项数量：1

## 2. 分数分布

| 分数段 | case 数 |
|---|---:|
| 90-100 | 0 |
| 80-89 | 0 |
| 60-79 | 1 |
| 0-59 | 0 |

## 3. 维度得分

| 维度 | 权重 | 平均得分 | 得分率 | 主要失分原因 |
|---|---:|---:|---:|---|
| 合规性 | 10.0 | 10.00 | 100.0% | 无 |
| 表达质量 | 30.0 | 25.00 | 83.3% | 无 |
| 任务完成度 | 30.0 | 30.00 | 100.0% | 部分细节不足 |

## 4. Case 明细

| case_id | 总分 | 是否通过 | 一票否决 | 缺失覆盖项 | 主要结论 |
|---|---:|---|---|---|---|
| case_001 | 65.00 | 否 | 否 | identity_confirmation, contract_effective_notification, delivery_willingness_confirmation, minimum_order_requirement, continuous_delivery_requirement, expression_natural_short | fake evaluation for graph validation |

## 5. 未覆盖项与证据

| case_id | missing_target | 缺失原因 |
|---|---|---|
| case_001 | identity_confirmation | 部分细节不足 |
| case_001 | contract_effective_notification | 部分细节不足 |
| case_001 | delivery_willingness_confirmation | 部分细节不足 |
| case_001 | minimum_order_requirement | 部分细节不足 |
| case_001 | continuous_delivery_requirement | 部分细节不足 |
| case_001 | expression_natural_short | 部分细节不足 |

## 6. 风险项

| case_id | risk_rule | severity | deduction | evidence |
|---|---|---|---:|---|
| case_001 | generic_expression_gap | low | 0.00 |  |

## 7. 改进建议

- 优先复查未通过的 1 个 case：case_001。
