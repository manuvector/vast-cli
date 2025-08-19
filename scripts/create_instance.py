#!/usr/bin/env python3
import os, sys, json, subprocess, pathlib

KEY_PATH = os.environ.get("KEY_PATH", os.path.expanduser("~/.ssh/vast_rsa"))
KEY_COMMENT = os.environ.get("KEY_COMMENT", "manuel@vast")
OFFER_QUERY = os.environ.get("OFFER_QUERY", "gpu_ram>=12")
IMAGE = os.environ.get("IMAGE", "ultralytics/yolov3:latest")
DISK_GB = os.environ.get("DISK_GB", "40")

def need(cmd):
    from shutil import which
    if not which(cmd):
        print(f"Missing dependency: {cmd}", file=sys.stderr)
        sys.exit(1)

def run_json(cmd_list):
    out = subprocess.check_output(cmd_list)
    return json.loads(out)

def run(cmd_list, check=True):
    return subprocess.run(cmd_list, check=check)

def ensure_key():
    p = pathlib.Path(KEY_PATH)
    pub = pathlib.Path(KEY_PATH + ".pub")
    if not p.exists() or not pub.exists():
        print(f"==> Generating SSH key at {KEY_PATH}")
        run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-C", KEY_COMMENT, "-f", KEY_PATH, "-N", ""])
    os.chmod(KEY_PATH, 0o600)
    return pub.read_text().strip()

def register_key(pub_key):
    print("==> Registering SSH public key with Vast (idempotent)")
    try:
        run(["vastai", "create", "ssh-key", pub_key], check=False)
    except Exception:
        pass

def pick_offer():
    print(f"==> Selecting an offer matching: {OFFER_QUERY}")
    arr = run_json(["vastai", "search", "offers", OFFER_QUERY, "-d", "-o", "dph", "--limit", "1", "--raw"])
    if not arr:
        print(f"No offer found for query: {OFFER_QUERY}", file=sys.stderr)
        sys.exit(1)
    offer_id = arr[0].get("id")
    print(f"    Offer selected: {offer_id}")
    return str(offer_id)

def create_instance(offer_id):
    print("==> Creating instance")
    out = subprocess.check_output([
        "vastai", "create", "instance", str(offer_id),
        "--image", IMAGE, "--disk", str(DISK_GB), "--raw"
    ])
    try:
        data = json.loads(out)
    except Exception:
        data = {}
    instance_id = (
        str(data.get("new_contract") or
            data.get("new_instance") or
            data.get("id") or
            data.get("new_contract_id") or "")
    )
    if not instance_id:
        print("Could not parse instance id from create response:\n" + out.decode(), file=sys.stderr)
        sys.exit(1)
    print(f"    Instance ID: {instance_id}")
    return instance_id

def get_conn_for_instance(instance_id):
    arr = run_json(["vastai", "show", "instances", "--raw"])
    rec = next((x for x in arr if str(x.get("id")) == str(instance_id)), None)
    if not rec:
        return None, None
    host = rec.get("ssh_host") or rec.get("ssh_addr")
    port = rec.get("ssh_port")
    if (not host or not port) and rec.get("ssh_url"):
        parts = str(rec["ssh_url"]).split(":")
        if len(parts) == 2:
            host = host or parts[0]
            port = port or parts[1]
    return host, port

def main():
    need("vastai"); need("ssh"); need("ssh-keygen")
    pubkey = ensure_key()
    register_key(pubkey)
    offer_id = pick_offer()
    instance_id = create_instance(offer_id)
    print("==> Waiting for instance to be ready...")
    import time
    for _ in range(120):
        host, port = get_conn_for_instance(instance_id)
        if host and port:
            ssh_cmd = f"ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -i {KEY_PATH} -p {port} root@{host}"
            print("==> SSH command:")
            print(ssh_cmd)
            sys.exit(0)
        time.sleep(5)
    print("Timed out waiting for instance SSH info.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
