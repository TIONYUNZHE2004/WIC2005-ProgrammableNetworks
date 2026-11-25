#!/usr/bin/env python3
"""Make the Week 7 lab API match a YAML intent file."""
import argparse
from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
import sys
import uuid

import requests
import yaml

from inventory import API, Client

VLANS = "/api/v1/vlans"
ACL = "/api/v1/acl/entries"
ACL_FIELDS = {"action", "src", "dst", "protocol", "port", "description"}


def acl_body(rule):
    """Drop the server's ID and fill in the API's defaults for comparison."""
    return {
        "action": rule["action"],
        "src": rule["src"],
        "dst": rule["dst"],
        "protocol": rule.get("protocol", "any"),
        "port": rule.get("port"),
        "description": rule.get("description", ""),
    }


def load_intent(path):
    """Validate the whole file before sending any requests."""
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or not re.fullmatch(
        r"[0-9]{4}", str(data.get("student_id_last4"))
    ):
        raise ValueError("Set student_id_last4 to four digits")
    nn = int(str(data["student_id_last4"])[-2:])
    block = ipaddress.IPv4Network(f"10.{nn}.0.0/16")
    if not isinstance(data.get("vlans"), list) or not isinstance(data.get("acl"), list):
        raise ValueError("Intent needs vlans and acl lists")

    vlans = {}
    for vlan in data["vlans"]:
        number, name = vlan["id"], vlan["name"]
        if type(number) is not int or not 2 <= number <= 4094 or number in vlans:
            raise ValueError(f"Invalid or duplicate VLAN ID: {number}")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            raise ValueError(f"Invalid name for VLAN {number}")
        vlans[number] = name

    acl = []
    for raw in data["acl"]:
        if not isinstance(raw, dict) or raw.keys() - ACL_FIELDS:
            raise ValueError("Invalid ACL fields")
        rule = acl_body(raw)
        if rule["action"] not in ("permit", "deny"):
            raise ValueError("ACL action must be permit or deny")
        for field in ("src", "dst"):
            if not isinstance(rule[field], str) or "/" not in rule[field]:
                raise ValueError(f"ACL {field} must be in CIDR form")
            if not ipaddress.IPv4Network(rule[field]).subnet_of(block):
                raise ValueError(f"ACL {field} must be inside {block}")
        if rule["protocol"] not in ("any", "tcp", "udp", "icmp"):
            raise ValueError("Invalid ACL protocol")
        port = rule["port"]
        if port is not None and (
            rule["protocol"] not in ("tcp", "udp")
            or type(port) is not int
            or not 1 <= port <= 65535
        ):
            raise ValueError("ACL port must be 1-65535 and use TCP or UDP")
        if not isinstance(rule["description"], str):
            raise ValueError("ACL description must be text")
        if rule in acl:
            raise ValueError(f"Duplicate ACL rule: {rule}")
        acl.append(rule)

    if len(vlans) < 6 or len(acl) < 4:
        raise ValueError("Intent needs at least six VLANs and four ACL rules")
    if {rule["action"] for rule in acl} != {"permit", "deny"}:
        raise ValueError("Intent needs both permit and deny rules")
    if not any(rule["port"] is not None for rule in acl):
        raise ValueError("At least one ACL rule needs a port")
    return vlans, acl


@dataclass
class Change:
    method: str
    path: str
    label: str
    body: dict | None = None


def read_state(client):
    vlans, _ = client.get_all(API + VLANS)
    acl, _ = client.get_all(API + ACL)
    vlan_names = {row["id"]: row["name"] for row in vlans if row["id"] != 1}
    return vlan_names, sorted(acl, key=lambda rule: rule["id"])


def plan_changes(current, desired):
    have_vlans, have_acl = current
    want_vlans, want_acl = desired
    plan = []
    for number, name in sorted(want_vlans.items()):
        old_name = have_vlans.get(number)
        if old_name != name:
            label = f"Create VLAN {number} {name}" if old_name is None else (
                f"Rename VLAN {number} from {old_name} to {name}"
            )
            plan.append(Change("PUT", f"{VLANS}/{number}", label, {"name": name}))
    for number in sorted(have_vlans.keys() - want_vlans.keys()):
        plan.append(Change("DELETE", f"{VLANS}/{number}", f"Delete VLAN {number} {have_vlans[number]}"))

    # The API appends rules. Keep the longest prefix we can match in order.
    retained = 0
    for rule in have_acl:
        if retained < len(want_acl) and acl_body(rule) == want_acl[retained]:
            retained += 1
        else:
            plan.append(Change("DELETE", f"{ACL}/{rule['id']}", f"Delete ACL entry {rule['id']}"))
    for rule in want_acl[retained:]:
        protocol = rule["protocol"]
        if rule["port"] is not None:
            protocol += f"/{rule['port']}"
        label = f"Add ACL {rule['action']} {rule['src']} to {rule['dst']} {protocol}"
        plan.append(Change("POST", ACL, label, rule))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intent", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    desired = load_intent(args.intent)
    client = Client()
    plan = plan_changes(read_state(client), desired)
    print(f"Plan: {len(plan)} change(s)")
    for change in plan:
        print(f"  {change.label}")
    if args.dry_run:
        print("Dry run: no configuration writes sent.")
        return

    for change in plan:
        # One key per planned create. All retries of that create share it.
        key = str(uuid.uuid4()) if change.method == "POST" else None
        result = client.request(change.method, API + change.path, body=change.body, key=key)
        replay = " (replayed)" if result.headers.get("Idempotent-Replayed") == "true" else ""
        print(f"Applied: {change.label} [HTTP {result.status_code}{replay}]")

    remaining = plan_changes(read_state(client), desired)
    if remaining:
        for change in remaining:
            print(f"  Still needed: {change.label}", file=sys.stderr)
        sys.exit("Verification failed: API state differs from intent.")
    print("Verified: API state matches intent.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError, requests.RequestException) as error:
        sys.exit(f"Sync failed: {error}")
