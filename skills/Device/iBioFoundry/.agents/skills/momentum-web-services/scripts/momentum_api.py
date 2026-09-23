import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape


def build_opener(scheme):
    handlers = [urllib.request.ProxyHandler({})]
    if scheme == "https":
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    return urllib.request.build_opener(*handlers)


def http_request(opener, url, method, body, headers, timeout=20):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def get_token(opener, base_url, username, password):
    payload = json.dumps({"Username": username, "Password": password}).encode("utf-8")
    status, body = http_request(
        opener,
        f"{base_url}/api/token/accesstoken",
        "POST",
        payload,
        {"Content-Type": "application/json", "Accept": "application/json"},
    )
    parsed = parse_json_maybe(body)
    token = parsed.get("token") if isinstance(parsed, dict) else None
    return status, body, token


def parse_json_maybe(body):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def print_result(status, body):
    print(f"HTTP {status}")
    parsed = parse_json_maybe(body)
    if isinstance(parsed, (dict, list)):
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    else:
        print(parsed)


def build_worklist_xml(process_name, workunit_name, variable_name, variable_value):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<worklist>
  <workunit name="{escape(workunit_name)}" append="false" auto_load="true" auto_unload="true">
    <batch process="{escape(process_name)}" iterations="1" name="{escape(workunit_name)} Batch">
      <variable name="{escape(variable_name)}">
        <value iteration="1">{escape(variable_value)}</value>
      </variable>
    </batch>
  </workunit>
</worklist>
'''


def run_worklist(opener, base_url, token, process_name, variable_name, variable_value):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workunit_name = f"API Test {process_name} {timestamp}"
    payload = build_worklist_xml(process_name, workunit_name, variable_name, variable_value).encode("utf-8")
    return http_request(
        opener,
        f"{base_url}/api/momentum/worklist",
        "POST",
        payload,
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
            "Accept": "application/json, text/plain, */*",
        },
    )


def run_workqueue(opener, base_url, token):
    return http_request(
        opener,
        f"{base_url}/api/momentum/workqueue",
        "GET",
        None,
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
        },
    )


def run_workqueue_by_id(opener, base_url, token, workunit_id):
    return http_request(
        opener,
        f"{base_url}/api/momentum/workqueue/{workunit_id}",
        "GET",
        None,
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Momentum Web Services helper.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", required=True)
    common.add_argument("--username", default="operator")
    common.add_argument("--password", default="#Administrator123456")
    common.add_argument("--scheme", default="https", choices=["https", "http"])
    common.add_argument("--port", type=int, default=443)

    token_parser = subparsers.add_parser("token", parents=[common])
    token_parser.set_defaults(action_name="token")

    worklist_parser = subparsers.add_parser("worklist", parents=[common])
    worklist_parser.add_argument("--process-name", required=True)
    worklist_parser.add_argument("--variable-name", default="Title")
    worklist_parser.add_argument("--variable-value", default="api_test")
    worklist_parser.set_defaults(action_name="worklist")

    workqueue_parser = subparsers.add_parser("workqueue", parents=[common])
    workqueue_parser.set_defaults(action_name="workqueue")

    workqueue_id_parser = subparsers.add_parser("workqueue-id", parents=[common])
    workqueue_id_parser.add_argument("--workunit-id", required=True)
    workqueue_id_parser.set_defaults(action_name="workqueue-id")

    args = parser.parse_args()
    base_url = f"{args.scheme}://{args.host}:{args.port}"
    opener = build_opener(args.scheme)

    status, body, token = get_token(opener, base_url, args.username, args.password)
    print("Token result:")
    print_result(status, body)
    if status != 200 or not token:
        return 1

    if args.action == "token":
        return 0

    if args.action == "worklist":
        status, body = run_worklist(
            opener,
            base_url,
            token,
            args.process_name,
            args.variable_name,
            args.variable_value,
        )
        print("\nWorklist result:")
        print_result(status, body)
        return 0 if 200 <= status < 300 else 1

    if args.action == "workqueue":
        status, body = run_workqueue(opener, base_url, token)
        print("\nWorkqueue result:")
        print_result(status, body)
        return 0 if 200 <= status < 300 else 1

    status, body = run_workqueue_by_id(opener, base_url, token, args.workunit_id)
    print("\nWorkqueue by id result:")
    print_result(status, body)
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
