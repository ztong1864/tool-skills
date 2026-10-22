# Source Code Handoff

本交接包是完整推理包；源码 zip 只是其中一部分。预测运行必须同时满足：

1. 保留完整 skill 包，尤其是 `primekg_cgi_graph_graph_only_e50/`。
2. 设置 `KG_PROJECT_SRC` 指向原模型源码的 `src` 目录。
3. 环境能导入 PyTorch、DGL、RDKit、pandas、numpy 等依赖。

## 方案 A：私有 GitHub 仓库授权

```text
repository: git@github.com:lulu754022140/KG-drug-efficacy-models.git
branch: feature/cgi-graph-e50-handoff-clean
commit: 69fef47 Prepare Graph CGI e50 handoff
```

克隆后设置：

```bash
export KG_PROJECT_SRC=/path/to/KG-drug-efficacy-models/src
```

## 方案 B：源码压缩包

如果不方便开放私有 GitHub 权限，使用随交接包提供的源码压缩包：

```text
source_archives/KG-drug-efficacy-models_feature-cgi-graph-e50-handoff-clean_69fef47.zip
```

解压示例：

```bash
mkdir -p /path/to/kg_drug_efficacy_source
unzip source_archives/KG-drug-efficacy-models_feature-cgi-graph-e50-handoff-clean_69fef47.zip -d /path/to/kg_drug_efficacy_source
export KG_PROJECT_SRC=/path/to/kg_drug_efficacy_source/src
```

然后在 skill 包目录验证：

```bash
bash verify_handoff.sh
PYTHONPATH=src:${KG_PROJECT_SRC} python -m primekg_cgi_graph_delivery.cli --help
bash score.sh 43789 score_43789.csv python cuda 20
```

## 注意事项

- 源码 zip 不包含模型权重和 prepared 数据，单独不能完成预测。
- 模型权重和 prepared 数据在 `primekg_cgi_graph_graph_only_e50/` 中。
- 只做推理时不需要原始 `kg.csv`、DrugBank XML、CMap/CGI 原始文件。
- 如果要重新 prepare 或重新训练，需要另行提供 PrimeKG、DrugBank、CMap/CGI 和 disease embedding 数据。
- 当前版本不支持 KG 外新药、任意 SMILES、天然产物库冷启动。
