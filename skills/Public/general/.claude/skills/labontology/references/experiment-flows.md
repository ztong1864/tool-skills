# Experiment flows (for device teams)

Each device has its own ontology Skill (for example `fdu-ontology` for the Fudan workstation, XmartChem). That Skill is
the entry point of experiments on the device: it says which Skills an experiment goes through, in which order, where a
review checks a result, where the user confirms, and where a request may stop. LabOntology reads this from one file in
the ontology Skill's folder and builds the mission plan from it (`run --flow`). Nothing in LabOntology is specific to a
device; a new device only adds its own file.

## The file

`experiment_flows.yaml` (or `.yml`) next to the ontology Skill's `SKILL.md`:

```yaml
schema: labontology.experiment-flow.v1
flows:
  - id: my-device-experiment          # used in `run --flow my-device-experiment`
    name: 我的设备：实验目标到设备任务
    description: 一句话说明这个流程做什么
    default_stop: protocol            # the stop used when the request does not say how far to go
    stops:                            # every stop named below, with what it means for the user
      plan: 只要实验方案
      protocol: 实验准备和方案生成：到设备协议，创建设备任务前停下
      device: 用户明确要求创建设备任务
    steps:
      - skill: constraint-parser
      - skill: literature-experiment-recommender
        review: my-risk-review        # a Skill that checks this step's result right after it
        pause: 请确认哪些推荐组合继续   # the user confirms here (after the review) before the flow goes on
      - skill: my-plan-writer
        stop: plan                    # `--until plan` ends the plan with this step
      - skill: my-protocol-builder
        pause: 请确认是否创建设备任务
        stop: protocol
      - skill: my-device-run
        stop: device
      - skill: my-monitor
        optional: true                # listed for reference; never put in a plan
```

Rules:

- `skill` and `review` are Skill ids of the same skill library (the folder ids `inspect --skills` lists). A flow naming
  a Skill the library does not have is listed with `missing_skills` and `run --flow` refuses it. (`worker`, the step
  key's earlier name, is still read.)
- A plan is the flow up to the chosen stop: each step's `skill`, then its `review`. The same review Skill may follow
  several steps; each review is its own plan step.
- `pause` makes the Runtime stop after that step (after its review) and ask the user, showing the step's result and the
  pause text; the user's next message is the answer. Steps without `pause` run on without asking. The pause of the
  plan's last step is asked when the plan is done, together with the command for the next step if the user agrees.
- A Skill that acts on a device (side effect other than read-only) still needs the user's explicit approval from the
  Runtime, whatever the flow says.
- A malformed file does not hide the ontology Skill: the problem is listed under `experiment_flow_problems` by `inspect`.
- After changing the device's flow (in the ontology's own graph or documents), update this file too; LabOntology picks it
  up the next time it prepares the library (`run`, `inspect` or `bootstrap`).
