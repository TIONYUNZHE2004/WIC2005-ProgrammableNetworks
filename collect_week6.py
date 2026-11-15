#!/usr/bin/env python3
"""Collect real Week 6 evidence in a fresh course container, from the repo root.

    python3 collect_week6.py --design overlay.yaml

Uses the course builder unchanged outside its two assignment functions. No pingall:
each check names a source VM and an IP within that VM's own department.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time

from mininet.log import setLogLevel

from build_overlay import build, check_mtu, check_spec, load, plan


EVIDENCE = Path("evidence6")
EVIDENCE.mkdir(exist_ok=True)
SUMMARY = EVIDENCE / "summary.json"


def write(file, text):
    with (EVIDENCE / file).open("a") as stream:
        stream.write(text.rstrip() + "\n\n")


def begin(file, title):
    (EVIDENCE / file).write_text(
        f"== {title}\nUTC: {datetime.now(timezone.utc).isoformat()}\n\n"
    )


def command(node, text, file, expected=0):
    out, err, code = node.pexec(text, shell=True)
    result = out + err
    write(file, f"$ {node.name} {text}\n{result}Exit code: {code}")
    if expected is not None and code != expected:
        raise RuntimeError(f"{node.name}: {text}: exit {code}, expected {expected}")
    return result, code


def ping(node, size, file, passes, count=1):
    _, code = command(
        node, f"ping -M do -c {count} -W 1 -s {size} 10.41.100.11",
        file, expected=None,
    )
    assert (code == 0) == passes, f"Unexpected ping result for payload {size}"


def capture(node, interface, expression=None):
    args = ["timeout", "5", "tcpdump", "-n", "-e", "-l", "-i", interface]
    if expression:
        args += expression
    proc = node.popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    header = ""
    while "listening on" not in header:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"tcpdump did not start: {header}")
        header += line
    return proc, header, f"$ {node.name} {' '.join(args)}"


def finish_capture(session, file):
    proc, header, label = session
    remaining, _ = proc.communicate(timeout=8)
    text = header + remaining
    assert proc.returncode == 124, f"tcpdump exited unexpectedly: {text}"
    write(file, label + "\n" + text + "Exit code: 124 (capture timer ended)")
    return text


def throughput(net, file, broken=False):
    server = net.get("it2").popen(
        ["iperf3", "-s", "-1"], stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True,
    )
    try:
        time.sleep(0.2)
        out, code = command(
            net.get("it1"), "timeout 12 iperf3 -c 10.41.100.11 -t 5",
            file, expected=None if broken else 0,
        )
        matches = re.findall(r"([\d.]+)\s+([KMGT]?)bits/sec[^\n]*receiver", out)
        if not broken:
            assert matches, "iperf did not report a receiver result"
        if matches:
            value, unit = matches[-1]
            return {"receiver": f"{value} {unit}bits/sec", "exit_code": code}
        return {"receiver": None, "exit_code": code}
    finally:
        if server.poll() is None:
            server.terminate()
        server.communicate(timeout=4)


def network(path, force=False):
    spec = load(path)
    assert not check_spec(spec), check_spec(spec)
    if not force:
        assert not check_mtu(spec), check_mtu(spec)
    print(f"Building fresh network: {path}", flush=True)
    with (EVIDENCE / "builds.txt").open("a") as build_log:
        build_log.write(f"\n== Fresh network: {path}\n")
        with redirect_stdout(build_log):
            net, _ = build(spec)
    return spec, net


def flood_and_isolation(path, summary):
    spec, net = network(path)
    try:
        begin("flood.txt", f"Flood and learn; fresh {path}")
        hv1, hv3 = net.get("hv1"), net.get("hv3")
        before, _ = command(hv1, "bridge fdb show dev vxlan100", "flood.txt")
        # bridge also prints the device's own permanent MACs; these are not remote VTEPs.
        entries = [line for line in before.splitlines() if " self " in line]
        assert len(entries) == 2 and all(line.startswith("00:00:00:00:00:00") for line in entries)
        session = capture(hv3, "hv3-eth0", ["udp", "port", "4789"])
        command(net.get("it1"), "ping -c 2 -W 1 10.41.100.11", "flood.txt")
        text = finish_capture(session, "flood.txt")
        assert "Request who-has 10.41.100.11" in text and "vni 100" in text
        after, _ = command(hv1, "bridge fdb show dev vxlan100", "flood.txt")
        third, _ = command(hv3, "bridge fdb show dev vxlan100", "flood.txt")
        assert "02:00:00:64:00:0b dst 10.41.0.2" in after
        assert "02:00:00:64:00:0a dst 10.41.0.1" in third

        begin("isolation.txt", "IT and BU both have 10.41.100.11")
        session = capture(net.get("bu2"), "bu2-eth0")
        command(net.get("it1"), "ping -c 3 -W 1 10.41.100.11", "isolation.txt")
        it_neigh, _ = command(net.get("it1"), "ip neigh show 10.41.100.11", "isolation.txt")
        other = finish_capture(session, "isolation.txt")
        assert "0 packets captured" in other
        command(net.get("bu1"), "ping -c 2 -W 1 10.41.100.11", "isolation.txt")
        bu_neigh, _ = command(net.get("bu1"), "ip neigh show 10.41.100.11", "isolation.txt")
        assert "02:00:00:64:00:0b" in it_neigh
        assert "02:00:00:c8:00:0b" in bu_neigh

        begin("connectivity.txt", "Every ordered VM pair within its own department")
        addresses = plan(spec)["vms"]
        count = 0
        for tenant in spec["tenants"]:
            for source, _ in tenant["vms"]:
                for target, _ in tenant["vms"]:
                    if source != target:
                        command(net.get(source), f"ping -c 1 -W 1 {addresses[target]['ip']}", "connectivity.txt")
                        count += 1
        summary["within_tenant_pairs_passed"] = count
        summary["flood_isolation_design"] = path
        summary["isolation"] = "IT and BU resolve the shared IP to different MACs; BU capture quiet during IT ping"
        print("PASS: flood, learning, tenant isolation and all 12 VM pairs", flush=True)
    finally:
        net.stop()


def blackhole(summary):
    _, net = network("blackhole.yaml", force=True)
    try:
        begin("blackhole.txt", "Forced MTU 1500 on both tenant and underlay")
        command(net.get("it1"), "ping -c 2 -W 1 10.41.100.11", "blackhole.txt")
        _, code = command(net.get("it1"), "ping -c 2 -W 1 -s 1472 10.41.100.11", "blackhole.txt", expected=None)
        assert code != 0, "Expected large packets to fail"
        summary["blackhole_iperf"] = throughput(net, "blackhole.txt", broken=True)
        low, high = 0, 1472
        while high - low > 1:
            size = (low + high) // 2
            _, code = command(net.get("it1"), f"ping -M do -c 1 -W 1 -s {size} 10.41.100.11", "blackhole.txt", expected=None)
            if code == 0:
                low = size
            else:
                high = size
        write("blackhole.txt", "== Confirm the adjacent passing and failing sizes")
        ping(net.get("it1"), low, "blackhole.txt", True)
        ping(net.get("it1"), high, "blackhole.txt", False)
        command(net.get("hv1"), "ip -d link show vxlan100", "blackhole.txt")
        summary["blackhole_largest_ping_data"] = low
        summary["blackhole_smallest_failing_ping_data"] = high
        print(f"PASS: black hole measured; ping data {low} passes, {high} fails", flush=True)
    finally:
        net.stop()


def fixes(summary):
    begin("fixes.txt", "Compare two MTU fixes on separate fresh networks")
    for label, path, limit in [("A", "mtu_a.yaml", 1422), ("B", "mtu_b.yaml", 1472)]:
        spec, net = network(path)
        try:
            write("fixes.txt", f"== Fix {label}: {path}; underlay MTU {spec['underlay']['mtu']}; tenant MTU {spec['tenants'][0]['mtu']}")
            ping(net.get("it1"), limit, "fixes.txt", True)
            ping(net.get("it1"), limit + 1, "fixes.txt", False)
            summary[f"fix_{label.lower()}"] = throughput(net, "fixes.txt")
            summary[f"fix_{label.lower()}"]["largest_ping_data"] = limit
            print(f"PASS: fix {label}: {summary[f'fix_{label.lower()}']}", flush=True)
        finally:
            net.stop()


def main():
    os.environ.setdefault("SHELL", "/bin/bash")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", default="overlay.yaml")
    parser.add_argument("--final-network-only", action="store_true")
    args = parser.parse_args()
    setLogLevel("error")
    summary = json.loads(SUMMARY.read_text()) if args.final_network_only else {}
    summary["run_utc"] = datetime.now(timezone.utc).isoformat()
    summary["environment"] = "User's WSL Ubuntu; firdaussahran/netlab-mininet:1.0 course container"
    if not args.final_network_only:
        begin("builds.txt", "Actual bridge and VXLAN commands for each fresh network")
        result = subprocess.run(["python3", "build_overlay.py", "blackhole.yaml"], capture_output=True, text=True)
        begin("check.txt", "Reject invalid MTU before building anything")
        write("check.txt", "$ python3 build_overlay.py blackhole.yaml\n" + result.stdout + result.stderr + f"Exit code: {result.returncode}")
        assert result.returncode != 0 and result.stdout.count("PROBLEM:") == 2
        assert "nothing was built" in result.stderr
    flood_and_isolation(args.design, summary)
    if not args.final_network_only:
        blackhole(summary)
        fixes(summary)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    print("ALL CHECKS PASSED\n" + json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
