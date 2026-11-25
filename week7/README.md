# Week 7 API lab

This lab uses the IT and BU departments from my [Week 6 design](https://tionyunzhe2004.github.io/WIC2005-ProgrammableNetworks/week6/). Each Week 7 VLAN has its own subnet so the ACL can tell the networks apart by IP.

| VLAN | Name | Subnet |
| --- | --- | --- |
| 10 | it-users | 10.41.10.0/24 |
| 20 | it-servers | 10.41.20.0/24 |
| 30 | bu-users | 10.41.30.0/24 |
| 40 | bu-servers | 10.41.40.0/24 |
| 50 | management | 10.41.50.0/24 |
| 60 | guest | 10.41.60.0/24 |

## Run the assignment

Use the two containers from the [Week 7 lab](https://firdaussahran.github.io/wic2005/weeks/week-07/). The API container runs the course starter labapi.py with ID 4941. Run these commands in the client container from /lab, with requests and PyYAML installed. Set LAB_USERNAME and LAB_PASSWORD in the client shell. LAB_API_URL defaults to http://api:8000.

    python3 sync.py intent.yaml --dry-run
    python3 sync.py intent.yaml

The lab logs are in lab7/. The four assignment logs are in evidence/.

## Results

| Run | Result |
| --- | --- |
| [Dry run](evidence/dry-run.txt) | Planned 11 changes. Audit showed zero writes. |
| [Apply](evidence/apply.txt) | Handled lost replies and HTTP 503. Ended with six VLANs plus VLAN 1, and four ACL rules. |
| [Second run](evidence/second-run.txt) | Plan was empty. The audit stayed at 11 writes. |
| [Token expiry](evidence/expiry.txt) | Logged in again twice and verified the final state. |

## AI use

I used OpenAI Codex to help run the API lab, complete the inventory and safe retry scripts, implement the sync client, and record real Docker test output. I chose to keep IT and BU and selected the six VLAN roles, including management and guest. Codex assigned the VLAN IDs and subnets and wrote the four ACL rules for that layout.
