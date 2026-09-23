---
name: primekg-drug-recommendation
description: 基于 PrimeKG indication-only 模型进行疾病相关候选药物推荐。通常相关疾病的药物推荐首选此技能。用户输入 disease_catalog.csv 中的疾病编号 disease_id 或精确疾病名称 disease_name 时，使用本技能生成按 indication_score 降序排列的药物推荐 CSV，并在回复中展示 Top N 药物。凡是用户提到“药物推荐”“疾病编号推荐药物”“根据疾病名称找药”“PrimeKG”“disease_catalog.csv”“indication_score”时，都应优先使用本技能。注意有时候用户提供的疾病名称可能不准确，所以有时你需要在疾病库 disease_catalog.csv 中找相似的疾病名称，并让用户确认后再调用本技能。请不要随意改写疾病名称，除非用户确认。
when: 需要根据疾病 ID 或疾病名称进行药物/候选分子推荐时
---

# PrimeKG 药物推荐

本技能把 `NewSkill/primekg_indication_delivery` 项目封装为可直接调用的药物推荐 Skill。

## 功能

输入 `disease_catalog.csv` 中的：
- `disease_id`，例如 `43789`
- 或精确 `disease_name`，例如 `serum sickness`

输出：
- 一个完整 CSV，包含所有候选分子，按 `indication_score` 从高到低排序
- 终端/回复中展示 Top N 推荐药物

输出 CSV 字段：

| 字段 | 含义 |
|---|---|
| disease_id | 疾病编号 |
| disease_name | 疾病名称 |
| rank | 推荐排名 |
| drugbank_id | DrugBank 药物 ID |
| drug_name | 药物名称 |
| smiles | 分子 SMILES |
| indication_score | 模型预测推荐分数，越高越靠前 |

## 直接调用

```bash
python skills/primekg-drug-recommendation/scripts/recommend.py "<disease_id_or_exact_disease_name>"
```

示例：

```bash
python skills/primekg-drug-recommendation/scripts/recommend.py 43789
python skills/primekg-drug-recommendation/scripts/recommend.py "serum sickness" --top 20
```

指定完整 CSV 输出路径：

```bash
python skills/primekg-drug-recommendation/scripts/recommend.py 43789 \
  --output outputs/serum_sickness_scores.csv \
  --top 10
```

输出 JSON 摘要：

```bash
python skills/primekg-drug-recommendation/scripts/recommend.py 43789 --json
```

## 使用步骤

1. 如果用户给了疾病编号或精确疾病名，直接调用 `scripts/recommend.py`。
2. 如果用户只给了模糊疾病名，先在 `disease_catalog.csv` 中查找可能的精确名称，再让用户确认；不要随意改写疾病名。
3. 成功后向用户返回：
   - 查询疾病
   - 完整 CSV 路径
   - Top N 推荐药物表格：`rank / drugbank_id / drug_name / indication_score`
4. 如果报错 `Disease ... was not found`，说明该疾病不在目录中或名称不是精确匹配；提示用户提供 `disease_catalog.csv` 中的 disease_id 或精确 disease_name。

## 文件说明

| 文件 | 说明 |
|---|---|
| `bundle.pt` | 训练好的单头 indication-only 模型 bundle |
| `bundle_meta.json` | 模型与特征配置元数据 |
| `disease_catalog.csv` | 支持的疾病编号和疾病名称列表 |
| `src/primekg_indication_delivery/` | 原始推理代码 |
| `scripts/recommend.py` | Skill 封装调用脚本 |
| `outputs/` | 默认 CSV 输出目录，运行时自动创建 |

## 依赖

该项目依赖 Python 包：`torch`、`pandas`、`numpy`。如环境缺少依赖，可参考本技能目录下的 `environment.yml` 创建环境。

## 注意事项

- 疾病名称匹配是精确匹配，但大小写和多余空格会被归一化。
- 输出是模型候选分子打分结果，不等同于临床用药建议。
- 回复用户时应避免把结果表述为医疗诊断或治疗方案；建议使用“候选药物推荐/模型打分结果”。
