# MOF Discovery Agent - Claude Code Skill直插版本

## Quick Start

可以直接在这个project打开claude code，输入用户需求开始mof材料推荐pipeline (开启planning-with-files skill)：
```
/planning-with-files 这个项目是关于构建MOF材料发现Agent的。请你进行候选推荐任务。候选推荐的步骤和skill保存在 @recomm_steps.md 文件中，请你首先重点仔细阅读该文件，了解完整候选推荐过程，严格依据它的步骤设计plan以进行候选推荐。
  
现在，用户的需求如下：“帮我设计同时具有高C3H6/C3H8动力学分离选择性且丙烯扩散非常快 (看扩散时间常数) 的最佳材料。”
```

也可以直接使用mof-recommendation skill（性能不保证，是LLM合成的）：
```
/mof-recommendation 帮我设计同时具有高C3H6/C3H8动力学分离选择性且丙烯扩散非常快 (看扩散时间常数) 的最佳材料。
```

## 文件简述

* .claude文件夹里面关于所有可用的研究技能，里面重点使用2个：planning-with-files和mof-recommendation。
* 相关文献是原始文献库。
* memory中记载了知识库KB。
* research-wiki是之前沉淀和总结的知识。
* recomm_steps.md是整个pipeline概述，是人工撰写的步骤，可转为skill