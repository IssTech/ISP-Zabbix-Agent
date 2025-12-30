# IBM Storage Protect Zabbix Agent Script

Advanced Monitoring for IBM Storage Protect (ISP) / TSM using Zabbix

This project provides a robust, Python-based solution to monitor IBM Storage Protect (formerly Tivoli Storage Manager) servers. Unlike simple scripts, this agent uses Zabbix Low-Level Discovery (LLD) to automatically detect Storage Pools, Drives, and Libraries, and employs Dependent Items to minimize load on the ISP database.

Features

Auto-Discovery: Automatically finds new Storage Pools and creates items/graphs for them.

Secure: Credentials are stored in a restricted configuration file, not in the script.

Efficient: Fetches multiple metrics (Usage & Capacity) in a single query to reduce `dsmadmc` overhead.

Compatibility: Works with Python 3.8+ (RHEL/CentOS 9+).

Robust: Handles `dsmadmc` timeouts, permission issues, and parsing errors gracefully.

Prerequisites

IBM Storage Protect Client: The `dsmadmc` executable must be installed on the Zabbix Server or Proxy.

ISP Admin User: A read-only administrator account on your ISP server (e.g., `zabbixmon`).

Python 3: (Version 3.8 or higher).

Installation

1. Deploy the Script

Place the python script in your Zabbix External Scripts directory (typically `/usr/lib/zabbix/externalscripts/`).
```
cp isp_monitor.py /usr/lib/zabbix/externalscripts/
chmod +x /usr/lib/zabbix/externalscripts/isp_monitor.py
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py
```

2. Configure Credentials

Create a secure configuration file to store your ISP login details.

File: /etc/zabbix/isp_monitor.conf
```
[isp]
user = zabbixmon
password = YourSecretPassword
dsmadmc = /usr/bin/dsmadmc
# Default server (can be overridden in Zabbix with -s flag)
server = TSM1
```

Secure the file:
It is critical that only the zabbix user can read this file containing passwords.
```
chown zabbix:zabbix /etc/zabbix/isp_monitor.conf
chmod 600 /etc/zabbix/isp_monitor.conf
```

3. Tuning Zabbix Server (CRITICAL)

IBM's dsmadmc command is heavy and often takes 5-10 seconds to execute. The default Zabbix timeout is 3-4 seconds, which causes the script to fail.

Edit your Zabbix Server (or Proxy) config: /etc/zabbix/zabbix_server.conf

Find and change the Timeout parameter:
```
Timeout=30
```

Restart Zabbix:
```
systemctl restart zabbix-server
```

Zabbix Frontend Configuration

Step 1: Macros

Go to Configuration → Hosts → [Your ISP Host] → Macros and add:

* `{$ISP_SERVER}` = `Your_TSM_Server_Name` (as defined in `dsm.sys`)

Step 2: Storage Pool Discovery

Create a Discovery Rule to automatically find pools.

* Name: `ISP Storage Pool Discovery`
* Type: `External check`
* Key: `isp_monitor.py["discovery_stgpool","","-s","{$ISP_SERVER}"]`
* Update interval: `1h`

Step 3: Item Prototypes

We use a Master Item to fetch data and Dependent Items to parse it. This ensures we only login to ISP once per pool.

A. Master Item (The Fetcher)

* Name: `Stats JSON for {#STGPOOL}`
* Type: `External check`
* Key: `isp_monitor.py["stgpool_stats","{#STGPOOL}","-s","{$ISP_SERVER}"]`

Type of information: Text (Important! Returns JSON)

History storage: Do not keep history

B. Dependent Item: Utilization

* Name: `Storage Pool {#STGPOOL} - Utilization`
* Type: `Dependent item`
* Master item: `Stats JSON for {#STGPOOL}`
* Key: `isp.stgpool.util[{#STGPOOL}]`

Type of information: Numeric (float)

* `Units: %`
* Preprocessing: `JSONPath` → `$.pct_utilized`

C. Dependent Item: Capacity

* `Name: Storage Pool {#STGPOOL} - Capacity`
* Type: `Dependent item`
* Master item: `Stats JSON for {#STGPOOL}`
* Key: `isp.stgpool.capacity[{#STGPOOL}]`
* Type of information: `Numeric (float)`
* Units: `B`

Preprocessing:
    * `JSONPath` → `$.est_capacity_mb`
    * `Custom multiplier` → `1048576` (Converts MB to Bytes)

Testing & Troubleshooting

CLI Testing

Always test as the zabbix user to verify permissions/paths.

Test Discovery:
```
sudo -u zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py discovery_stgpool
# Output: {"data": [{"{#STGPOOL}": "DEDUPPOOL"}, ...]}
```

Test Stats for a specific pool:
```
sudo -u zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py stgpool_stats DEDUPPOOL -s TSM_SERVER
# Output: {"pct_utilized": 85.5, "est_capacity_mb": 299932642.0}
```

Common Errors

1. "Timeout while executing a shell script"
Cause: Zabbix killed the script before it finished.
Fix: You skipped "Installation Step 3". Edit `/etc/zabbix/zabbix_server.conf` and set `Timeout=30`.

2. "Value is not a number"
Cause: Your Master Item is set to "Numeric" instead of "Text".
Fix: Change the Master Item type to "Text" so it can accept the JSON string.