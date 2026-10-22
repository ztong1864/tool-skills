# Troubleshooting


## 线上 venv 与 DGL 依赖检查

线上 Oasis 技能使用已有 Python venv，不使用 Conda：

```bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
python -c "import sys; print(sys.executable); print(sys.version)"
python -c "import torch, pandas; from rdkit import Chem; print('torch', torch.__version__)"
```

推理源码还必须导入 DGL。当前服务端 venv 已核验为 Python 3.10.22、PyTorch 1.13.1+cpu、NumPy 1.24.3、pandas 2.0.3、scikit-learn 1.3.2 和 RDKit 2022.09.5，但尚未安装 DGL。因此 `verify_handoff.sh` 和正式推理会因缺少 DGL 失败；这是未满足运行依赖，不是 venv 与技能不匹配。安装并验证兼容的 DGL 前，不要把推理报告为成功，也不要删除 DGL 检查。

`environment.yml` 是服务端 venv 信息清单，不应用 `conda env create` 创建环境。`model_source/environment_dyz.yml` 和 SLURM 脚本属于模型开发/训练参考，不是此在线推理技能的运行环境。

## Cannot import the model package

Set `KG_PROJECT_SRC` to the original KG-project `src` directory:

```bash
export KG_PROJECT_SRC=/path/to/KG-project/src
```

## Disease not found

Check supported diseases:

```bash
PYTHONPATH=src python -m primekg_cgi_graph_delivery.cli list-diseases   --prepared-dir ./primekg_cgi_graph_graph_only_e50/prepared   --output supported_diseases.csv
```

Use exact disease name or disease ID.

## Disease name is ambiguous

Use the disease ID printed in the error message.

## CUDA is unavailable

Use `--device auto` or `--device cpu`, or run on a CUDA host.

## Unknown DrugBank IDs

The optional candidate file can only contain IDs present in `candidate_pool.csv`. This package does not support KG-external cold-start drugs.

## Empty output

Confirm the candidate filter is not empty and every requested DrugBank ID exists in `candidate_pool.csv`.

## PyTorch 2.6+ bundle 加载说明

该交接包加载的是本地可信训练 bundle。PyTorch 2.6+ 默认 `torch.load(weights_only=True)` 可能拒绝包含 pandas DataFrame 的旧式 bundle；调用程序已在本地可信 bundle 加载路径中显式使用兼容加载。不要把这个加载逻辑用于不可信来源的 checkpoint。


## Server code is not aligned with the handoff branch

Check the source branch or copied files first:

```bash
cd /slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG
PYTHONPATH=src python -m primekg_graph_indication_multitoken_cgi_graph.cli --help
python -m py_compile src/primekg_graph_indication_multitoken_cgi_graph/*.py
```

The expected GitHub branch is `feature/cgi-graph-e50-handoff-clean` at commit `69fef47`. If the server directory is a git checkout, use `git fetch origin` and checkout that branch. If it is not a git checkout, copy the full `src/primekg_graph_indication_multitoken_cgi_graph` folder from the branch, not only individual files.

## Waiting for a compute node

Use these SLURM checks while waiting:

```bash
squeue -u zhangjinlu --start
sinfo -p a10
```

`PD (Priority)` means the job is pending for scheduling priority. `R` means it is running. Do not run model eval on the login node while waiting.
