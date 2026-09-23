---
name: momentum-import-process
description: Upload generated Momentum experiment script `.txt` files to the target Momentum host and import them through the B-machine desktop agent workflow. Use when a local experiment script has already been generated and needs to be transferred to the target host, queued for import, and polled until completion.
when: Use after a Momentum experiment script `.txt` file has been generated and needs to be uploaded to the target Momentum host, queued for desktop-agent import, and polled until completion.
---

# Momentum Process Import

Use this skill after a Momentum experiment script `.txt` file has already been generated and needs to be uploaded to the target host and imported into Momentum through the B-machine desktop agent.

## Default Endpoints

- B host: `100.65.75.32`
- SSH account: `admin`
- SSH password: `Admin`
- Default remote root: `D:\IB`
- Recommended remote script directory: `<remote-root>\process_scripts`
- Recommended queue import script: `<remote-root>\import-process.ps1`
- Recommended job query script: `<remote-root>\get-import-process-job.ps1`
- Default timeout: `120` seconds
- Poll interval: `2` to `3` seconds

## Remote Root Override

By default this skill assumes the remote file layout lives under `D:\IB`. If the user explicitly provides another root directory such as `D:\AI_IB`, keep the same internal structure and remap the paths as:

- Script directory: `<remote-root>\process_scripts`
- Import script: `<remote-root>\import-process.ps1`
- Job query script: `<remote-root>\get-import-process-job.ps1`
- Desktop agent startup script: `<remote-root>\start-agent.ps1`

If the user gives a custom root, prefer passing `--remote-root <path>` to the bundled script. Only pass `--script-root`, `--importer`, or `--job-query` separately when the remote layout is not uniform.

## Required Preconditions On B

State these prerequisites before running the import, because the queued job still depends on the B-machine desktop session:

- B is logged into the Windows desktop
- B is not locked
- Momentum is already open
- The local desktop agent is already started on B with:

```powershell
powershell -ExecutionPolicy Bypass -File <remote-root>\start-agent.ps1
```

Do not call `<remote-root>\run-local-import.ps1` directly from A over SSH. GUI automation must be executed by the B-machine desktop agent, not by the SSH session.

## Preferred Workflow

1. Confirm the local `.txt` script exists and keep only its basename as the remote script name.
2. Resolve the remote root. Use `D:\IB` by default, or a user-specified root if provided.
3. Upload the `.txt` file to `<remote-root>\process_scripts` on `100.65.75.32`.
4. Queue the import job by calling `<remote-root>\import-process.ps1 -ScriptName <file name>`.
5. Poll `<remote-root>\get-import-process-job.ps1 -JobId <jobId>` every `2` to `3` seconds until:
   - `status = completed` and `exitCode = 0`, or
   - `status = failed`, or
   - the overall timeout expires
6. Parse the returned `jobId`.

## Success And Failure Rules

- Success: `status = completed` and `exitCode = 0`
- Failure: `status = failed`
- Continue polling: `status = queued` or `status = processing`
- Timeout: stop polling after the configured timeout, usually `120` seconds

When a job fails, inspect:

- `status`
- `exitCode`
- `error`

## Bundled Script

Prefer the bundled script for real uploads because it handles password SSH/SFTP, queue submission, and polling:

```powershell
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt
```

Useful options:

```powershell
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt --timeout-seconds 180
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt --poll-seconds 3
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt --remote-name custom_name.txt
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt --remote-root D:\AI_IB
python .agents\skills\momentum-import-process\scripts\upload_and_import.py path\to\script.txt --dry-run
```

If `paramiko` is missing, run the script from an environment that already has `paramiko`, such as `skills-env`, or install it first.

## Raw SSH Form

Queue the import task after the file has already been uploaded to `<remote-root>\process_scripts\single_plate_enzyme_assay.txt`:

```powershell
ssh admin@100.65.75.32 "powershell -ExecutionPolicy Bypass -File <remote-root>\import-process.ps1 -ScriptName single_plate_enzyme_assay.txt"
```

Query the task state:

```powershell
ssh admin@100.65.75.32 "powershell -ExecutionPolicy Bypass -File <remote-root>\get-import-process-job.ps1 -JobId <jobId>"
```

## Queue Result Interpretation

Queue submission returns JSON like:

```json
{
  "status": "queued",
  "message": "Job created.",
  "jobId": "<jobId>",
  "script": "single_plate_enzyme_assay.txt",
  "timestamp": "2026-04-15T19:56:02"
}
```

Completed job query returns JSON like:

```json
{
  "jobId": "<jobId>",
  "agentVersion": "2",
  "type": "import-process",
  "scriptName": "single_plate_enzyme_assay.txt",
  "scriptPath": "<remote-root>\\process_scripts\\single_plate_enzyme_assay.txt",
  "requestedAt": "...",
  "startedAt": "...",
  "completedAt": "...",
  "exitCode": 0,
  "status": "completed",
  "queueFile": "<remote-root>\\queue\\done\\<jobId>.json"
}
```

Treat `status = failed`, nonzero `exitCode`, or timeout as a failed import.
