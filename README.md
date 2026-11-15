# WIC2005 lab portfolio

Weeks 2 and 3 are in their existing folders. Week 6 uses the files at the repository root.

## Week 6 design

I chose four servers and two departments, IT and BU. IT has one VM on hv1, hv2 and hv3. BU has one VM on hv2, hv3 and hv4. Both departments use 10.41.100.0/24. IT uses VNI 100; BU uses VNI 200. The server network is 10.41.0.0/24.

The initial design uses MTU 1500 everywhere. `blackhole.yaml` keeps this design for the failure test. The two MTU fixes will be compared before I choose the final setting.

## AI use

I used OpenAI Codex to explain the assignment and present design choices as MCQs. I chose the server count, VM placement, department names, shared subnet and VNIs. Codex helps implement the two required functions and collect evidence in my WSL/Docker course environment. The course supplies `build_overlay.py` and `make_page6.py` as starter files. The final notes will identify the tests and writing assistance used.
