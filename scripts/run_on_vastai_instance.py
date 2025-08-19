#!/usr/bin/env python3
import os, sys, json, time, socket, subprocess, shlex, pathlib

# ---------------- Config (override via env) ----------------
KEY_PATH = os.environ.get("KEY_PATH", os.path.expanduser("~/.ssh/vast_rsa"))
KEY_COMMENT = os.environ.get("KEY_COMMENT", "manuel@vast")
OFFER_QUERY = os.environ.get("OFFER_QUERY", "gpu_ram>=12")  # e.g. 'gpu_name=RTX_3090 & dph<=0.5'
IMAGE = os.environ.get("IMAGE", "nvidia/cuda:12.2.0-runtime-ubuntu22.04")
DISK_GB = os.environ.get("DISK_GB", "20")


#SSH_CMD = os.environ.get("SSH_CMD", "nvidia-smi")          # remote command to run
POLL_SECS = int(os.environ.get("POLL_SECS", "5"))
TIMEOUT_SECS = int(os.environ.get("TIMEOUT_SECS", "600"))  # 10 min
SSH_CMD='nvidia-smi'


# ---------------- Helpers ----------------
def need(cmd):
    if not shutil_which(cmd):
        print(f"Missing dependency: {cmd}", file=sys.stderr)
        sys.exit(1)

def shutil_which(cmd):
    from shutil import which
    return which(cmd)

def run_json(cmd_list):
    out = subprocess.check_output(cmd_list)
    return json.loads(out)

def run(cmd_list, check=True):
    return subprocess.run(cmd_list, check=check)

def tcp_ready(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False

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
    # If it already exists, Vast may return success or an error we can ignore.
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

def get_existing_instance():
    """Return first running instance id, or None if none exist."""
    try:
        arr = run_json(["vastai", "show", "instances", "--raw"])
    except Exception:
        return None
    if not arr:
        return None
    # pick the first one in "running" state
    for inst in arr:
        if inst.get("actual_status") == "running":
            return str(inst["id"])
    return None


def create_instance(offer_id):
    print("==> Creating instance")
    # Different CLI versions return different fields; handle them all.
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

def show_ssh_command():
    instance_id = get_existing_instance()
    if not instance_id:
        print("No running instance found.", file=sys.stderr)
        sys.exit(1)
    host, port = get_conn_for_instance(instance_id)
    if not host or not port:
        print("Could not retrieve SSH connection info.", file=sys.stderr)
        sys.exit(1)
    ssh_cmd = f"ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -i {KEY_PATH} -p {port} root@{host}"
    print(ssh_cmd)


def get_conn_for_instance(instance_id):
    arr = run_json(["vastai", "show", "instances", "--raw"])
    rec = next((x for x in arr if str(x.get("id")) == str(instance_id)), None)
    if not rec:
        return None, None
    host = rec.get("ssh_host") or rec.get("ssh_addr")
    port = rec.get("ssh_port")
    # Some versions expose a combined .ssh_url like "host:port"
    if (not host or not port) and rec.get("ssh_url"):
        parts = str(rec["ssh_url"]).split(":")
        if len(parts) == 2:
            host = host or parts[0]
            port = port or parts[1]
    return host, port

def wait_for_ssh(instance_id):
    print(f"==> Waiting for SSH to become ready (timeout: {TIMEOUT_SECS}s)...")
    start = time.time()
    host = port = None
    while True:
        host, port = get_conn_for_instance(instance_id)
        if host and port and tcp_ready(host, port, timeout=2.0):
            print(f"    SSH ready at {host}:{port}")
            return host, port
        if time.time() - start > TIMEOUT_SECS:
            print(f"Timed out waiting for SSH. Last seen host={host} port={port}", file=sys.stderr)
            sys.exit(1)
        time.sleep(POLL_SECS)

def ssh_run(host, port, key_path, cmd):
    print(f"==> Running on {host}:{port} : {cmd}")
    ssh = [
        "ssh",
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-i", key_path,
        "-p", str(port),
        f"root@{host}",
        "--", cmd
    ]
    return subprocess.call(ssh)

# ---------------- Main ----------------
def main():
    need("vastai"); need("ssh"); need("ssh-keygen")

    pubkey = ensure_key()
    register_key(pubkey)

    instance_id = get_existing_instance()
    if instance_id:
        print(f"==> Using existing instance {instance_id}")
    else:
        offer_id = pick_offer()
        instance_id = create_instance(offer_id)

    host, port = wait_for_ssh(instance_id)
    rc = ssh_run(host, port, KEY_PATH, SSH_CMD)
    sys.exit(rc)
    
    #show_ssh_command()#'''
if __name__ == "__main__":
    main()

