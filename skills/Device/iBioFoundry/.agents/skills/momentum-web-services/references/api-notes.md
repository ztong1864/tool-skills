# Momentum Web Services API Notes

## Validated endpoints

### 1. POST /api/token/accesstoken

Request body:

```json
{
  "Username": "operator",
  "Password": "#Administrator123456"
}
```

Response shape:

```json
{
  "token": "<jwt>"
}
```

Notes:

- Use `Content-Type: application/json`.
- Use HTTPS.
- The target host may present a self-signed certificate.

### 2. POST /api/momentum/worklist

Validated request format:

```xml
<?xml version="1.0" encoding="utf-8"?>
<worklist>
  <workunit name="API Test Single_Plate_Enzyme_Assay 20260415T071348Z" append="false" auto_load="true" auto_unload="true">
    <batch process="Single_Plate_Enzyme_Assay" iterations="1" name="API Test Single_Plate_Enzyme_Assay 20260415T071348Z Batch">
      <variable name="Title">
        <value iteration="1">api_test</value>
      </variable>
    </batch>
  </workunit>
</worklist>
```

Notes:

- Send the XML body with `Content-Type: text/plain`.
- `text/xml` and `application/xml` returned `415 Unsupported Media Type` on the validated target host.
- `process="Single_Plate_Enzyme_Assay"` returned `200` with `workUnitsSubmitted`.
- `process="Single_Plate_Enzyme_Assay.esc"` returned `400` with `Can't add work unit - No workunits exist.`
- Include `Authorization: Bearer <token>`.

Success response example:

```json
{
  "workUnitsSubmitted": [
    {
      "id": "8e2cf944-629e-4364-a88c-5dc6cf626f22",
      "name": "API Test Single_Plate_Enzyme_Assay 20260415T071348Z"
    }
  ]
}
```

### 3. GET /api/momentum/workqueue

Notes:

- Include `Authorization: Bearer <token>`.
- Response is JSON.

Example response:

```json
{
  "state": "Idle",
  "workUnits": []
}
```

### 4. GET /api/momentum/workqueue/{id}

Notes:

- Include `Authorization: Bearer <token>`.
- Use the work unit id returned from `worklist` or listed by `workqueue`.
- Response is JSON for a single work unit.

Validated response example:

```json
{
  "id": "db600535-881f-408c-8be9-d0e0fc4a01ed",
  "contentType": "Worklist",
  "author": "Admin",
  "creationTime": "2026-04-16T03:54:29.1785974Z",
  "name": "API Test Single_Plate_Enzyme_Assay 20260416T035426Z",
  "isAborted": false,
  "isLoaded": false,
  "startTime": "0001-01-01T00:00:00",
  "completeTime": "0001-01-01T00:00:00",
  "state": "Waiting"
}
```

## Environment notes

- Use the `skills-env` conda environment for Python.
- Disable proxies explicitly for outbound HTTP requests.
- Skip TLS verification because the deployment may use a self-signed certificate.
