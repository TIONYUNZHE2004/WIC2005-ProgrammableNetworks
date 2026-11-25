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

## Results

| Run | Result |
| --- | --- |
| [Dry run](evidence/dry-run.txt) | Planned 11 changes. Audit showed zero writes. |
| [Apply](evidence/apply.txt) | Handled lost replies and HTTP 503. Ended with six VLANs plus VLAN 1, and four ACL rules. |
| [Second run](evidence/second-run.txt) | Plan was empty. The audit stayed at 11 writes. |
| [Token expiry](evidence/expiry.txt) | Logged in again twice and verified the final state. |

## E4 answers

### 1. How does the script decide what to change?

The script reads the VLANs and ACLs from the API and compares them with `intent.yaml`. In the test, it created VLAN 30 for BU users and renamed VLAN 10 from `users` to `it-users`. It removed VLAN 99 because it was missing from the file. One ACL rule blocks guest traffic from reaching the management subnet. After applying the changes, the script reads both lists again to check the result.

### 2. Which requests can the script retry?

`GET` only reads data. `PUT` sets the VLAN to the same value again. If a `DELETE` retry gets `404`, the item is already gone. An ACL `POST` needs the same key and body on every retry. The script waits on `429`, backs off after a `503` or a lost reply, and logs in again when the token expires. It stops on other errors or when it reaches the retry limit.

### 3. Why does an ACL POST need a key?

The VLAN ID is known before the request, so the script can use `PUT`. The API gives an ACL entry its ID when it processes the `POST`. The script makes one key for each new entry and reuses it for every retry. A new key on each attempt can add duplicates. Reusing an old key for a new change can return an old result or fail if the body changed.

### 4. What happens if two people run the script at the same time?

Both scripts can read the same settings and make different plans. One can overwrite the other’s changes. The API should check the configuration version and apply the whole plan in one step. If the version changed, it should reject the plan. The script can then read the latest settings and plan again.

### 5. Where are the credentials?

The script reads the login details from `LAB_USERNAME` and `LAB_PASSWORD`. It keeps the token in memory while it runs. A scan of the Week 7 Git history found no lab passwords or live tokens.

## AI use

I used ChatGPT (Codex) for VLAN and ACL suggestions and to troubleshoot the Docker lab. It also helped write and test the Python scripts and draft the README. I chose the VLAN roles and the version check for concurrent runs.
