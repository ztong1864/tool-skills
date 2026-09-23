---
name: momentum-web-services
description: Authenticate to Thermo Fisher Momentum Web Services and operate the validated token, worklist, workqueue, and workqueue-by-id APIs. Use when a user asks in natural language to start a Momentum process by giving a process name and target host IP, to check the Momentum work queue by giving a target host IP, or to inspect a specific work unit by giving a target host IP and work unit id. This skill should obtain an access token first, then call /api/momentum/worklist for launch requests, /api/momentum/workqueue for queue-status requests, and /api/momentum/workqueue/{id} for item-specific status requests.
when: Use when starting a Momentum process through Web Services, checking the Momentum work queue, or inspecting a specific work unit by host IP and work unit id.
---

# Momentum Web Services

Use the bundled script for every API call instead of rebuilding requests by hand.

## Workflow

1. Parse the user's request.
2. Extract the target host IP.
3. Decide the action:
   - If the user gives a process name and a host IP, treat the request as a launch request and call `worklist`.
   - If the user gives a host IP and a work unit id, or explicitly asks for a specific queue item, call `workqueue/{id}`.
   - If the user gives only a host IP or asks for queue state/status, call `workqueue`.
4. Obtain a token first by calling `accesstoken`.
5. Return the API result clearly. Include HTTP status and the parsed response body.

## Defaults

- Use `https` on port `443` unless the user explicitly overrides it.
- Use Momentum credentials `operator` / `#Administrator123456` unless the user supplies different Momentum credentials.
- Expect a self-signed certificate and disable certificate verification in the bundled script.
- Disable proxies for the request path. This environment may expose a broken HTTPS proxy that blocks direct calls to the target host.

## Launch A Process

Run the bundled script with the `worklist` action.

Example:

```powershell
conda run -n skills-env python C:\Users\34209\.codex\skills\momentum-web-services\scripts\momentum_api.py worklist --host 100.65.75.32 --username operator --password '#Administrator123456' --process-name Single_Plate_Enzyme_Assay
```

Use these launch rules:

- Send the XML worklist payload as `text/plain`.
- Set `append="false"`, `auto_load="true"`, and `auto_unload="true"` on the generated `workunit` unless the user gives a reason to change them.
- Default the variable to `Title=api_test` unless the user provides another variable name/value.
- Prefer the process name exactly as given by the user. If the user is unsure whether the process name needs an extension, try the exact name first.

## Check Queue Status

Run the bundled script with the `workqueue` action.

Example:

```powershell
conda run -n skills-env python C:\Users\34209\.codex\skills\momentum-web-services\scripts\momentum_api.py workqueue --host 100.65.75.32 --username operator --password '#Administrator123456'
```

## Check Queue Status By Work Unit Id

Run the bundled script with the `workqueue-id` action.

Example:

```powershell
conda run -n skills-env python C:\Users\34209\.codex\skills\momentum-web-services\scripts\momentum_api.py workqueue-id --host 100.65.75.32 --username operator --password '#Administrator123456' --workunit-id db600535-881f-408c-8be9-d0e0fc4a01ed
```

Use this when the user asks about a specific submitted item rather than the whole queue.

## Reference Material

Read [references/api-notes.md](references/api-notes.md) when you need the validated request format, content type, or example responses.
