# WIC2005 lab portfolio

Weeks 2 and 3 are in their existing folders. Week 6 uses the files at the repository root.

## Week 6 design

I chose four servers and two departments, IT and BU. IT has one VM on hv1, hv2 and hv3. BU has one VM on hv2, hv3 and hv4. Both departments use 10.41.100.0/24. IT uses VNI 100; BU uses VNI 200. The server network is 10.41.0.0/24.

I chose Fix A: VM MTU 1450 and underlay MTU 1500. This keeps the underlay settings. `blackhole.yaml` keeps the original MTU 1500 everywhere. `mtu_a.yaml` and `mtu_b.yaml` contain the two fixes.

## Run Week 6

From this repository's root in WSL:

```sh
docker run --rm -it --privileged -v "$PWD:/lab" -w /lab firdaussahran/netlab-mininet:1.0 bash
python3 build_overlay.py overlay.yaml
```

Exit Mininet before running another network. To collect fresh evidence and generate the page inside the course container:

```sh
python3 collect_week6.py
python3 make_page6.py overlay.yaml
```

The collector records commands and real outputs in `evidence6/`. It builds a fresh network for each experiment. It checks all 12 ordered VM pairs within their own departments, flood-and-learn, tenant isolation, the black hole and both MTU fixes. Overlapping addresses make `pingall` unsuitable here.

The five answers are in `page6.yaml`. The page includes the network diagram, generated VTEP commands and raw evidence. It is published at <https://tionyunzhe2004.github.io/WIC2005-ProgrammableNetworks/week6/>.

## AI use

I used OpenAI Codex to explain the assignment and present design choices as MCQs. I chose the server count, VM placement, department names, shared subnet, VNIs and Fix A, with the reason for that choice.

Codex implemented `tenant_commands()` and `check_mtu()`, wrote the evidence collector, and ran it in my WSL/Docker course environment. Codex drafted the short answers from my design choices and the real measurements, and helped generate and check the page. This was assisted work; the captures and command outputs were not invented.

The course supplies `build_overlay.py` and `make_page6.py` as starter files. The page generator is unchanged. Only the two required functions in the builder were completed; the extra collector automates the evidence commands.
