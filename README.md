# IBM Storage Protect Zabbix Monitoring Agent

Advanced Monitoring for IBM Storage Protect (ISP) / TSM using Zabbix

This project provides a robust, Python-based solution to monitor IBM Storage Protect (formerly Tivoli Storage Manager) servers. Unlike simple scripts, this agent uses Zabbix Low-Level Discovery (LLD) to automatically detect Storage Pools, Drives, and Libraries, and employs Dependent Items to minimize load on the ISP database.

## Features

- **Auto-Discovery**: Automatically finds new Storage Pools and creates items/graphs for them
- **Secure**: Credentials are stored in a restricted configuration file, not in the script
- **Efficient**: Fetches multiple metrics (Usage & Capacity) in a single query to reduce dsmadmc overhead
- **Compatibility**: Works with Python 3.6+ (RHEL/CentOS 7+)
- **Robust**: Handles dsmadmc timeouts, permission issues, and parsing errors gracefully

## Prerequisites

- **IBM Storage Protect Client**: The dsmadmc executable must be installed on the Zabbix Server or Proxy
- **ISP Admin User**: A read-only administrator account on your ISP server (e.g., zabbixmon)
- **Python 3**: Version 3.6 or higher

## Installation

### 1. Deploy the Script

Place the python script in your Zabbix External Scripts directory (typically `/usr/lib/zabbix/externalscripts/`):

```bash
cp isp_monitor.py /usr/lib/zabbix/externalscripts/
chmod +x /usr/lib/zabbix/externalscripts/isp_monitor.py
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py
```

### 2. Configure Credentials

Create a secure configuration file at `/etc/zabbix/isp_monitor.conf`:

```ini
[isp]
user = zabbixmon
password = YourSecretPassword
dsmadmc = /usr/bin/dsmadmc
server = TSM1
```

Secure the file (critical - only zabbix user can read):

```bash
chown zabbix:zabbix /etc/zabbix/isp_monitor.conf
chmod 600 /etc/zabbix/isp_monitor.conf
```

### 3. Tune Zabbix Server (CRITICAL)

Edit `/etc/zabbix/zabbix_server.conf` and set:

```
Timeout=30
```

Then restart:

```bash
systemctl restart zabbix-server
```

## Zabbix Frontend Configuration

### Step 1: Add Host Macros

Add `{$ISP_SERVER}` macro with your TSM server name.

### Step 2: Create Discovery Rule

- **Name**: ISP Storage Pool Discovery
- **Type**: External check
- **Key**: `isp_monitor.py["discovery_stgpool","","-s","{$ISP_SERVER}"]`
- **Update interval**: 1h

### Step 3: Item Prototypes

Create a Master Item and Dependent Items to parse JSON data efficiently.

**Master Item**:
- **Key**: `isp_monitor.py["stgpool_stats","{#STGPOOL}","-s","{$ISP_SERVER}"]`
- **Type**: Text

**Dependent Item - Utilization**:
- **Key**: `isp.stgpool.util[{#STGPOOL}]`
- **Preprocessing**: JSONPath → `$.pct_utilized`

**Dependent Item - Capacity**:
- **Key**: `isp.stgpool.capacity[{#STGPOOL}]`
- **Preprocessing**: JSONPath → `$.est_capacity_mb`, then multiply by 1048576

## Testing

```bash
# Test discovery
sudo -u zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py discovery_stgpool

# Test stats
sudo -u zabbix /usr/lib/zabbix/externalscripts/isp_monitor.py stgpool_stats DEDUPPOOL -s TSM_SERVER
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Timeout while executing a shell script" | Script timeout too short | Set `Timeout=30` in zabbix_server.conf |
| "Permission denied" | dsmadmc log write failure | Script sets `DSM_LOG=/tmp` automatically |
| "Value is not a number" | Master Item type is Numeric | Change Master Item type to Text |
Which format should this be converted to? Examples: reStructuredText (RST), AsciiDoc, HTML, or plain text. Provide the target format and any specific style preferences.