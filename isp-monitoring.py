#!/usr/bin/env python3
import subprocess
import sys
import csv
import io
import json
import argparse
import configparser
import os

# --- DEFAULTS ---
DEFAULT_CONFIG_PATH = "/etc/zabbix/isp_monitor.conf"

# --- PRE-DEFINED QUERIES ---
QUERIES = {
    # --- SINGLE VALUE CHECKS (Standard Items) ---
    "db_util": "select cast((100 - (free_space_mb*100) / tot_file_system_mb) as decimal(5,2)) from db",
    "log_util": "select cast((100 - (free_space_mb*100) / total_space_mb) as decimal(5,2)) from log",
    "session_count": "select count(*) from sessions",
    
    # --- DISCOVERY QUERIES (For LLD) ---
    "discovery_stgpool": "select stgpool_name from stgpools",
    
    # --- PARAMETERIZED CHECKS (Item Prototypes) ---
    "stgpool_util": "select pct_utilized from stgpools where stgpool_name='{0}'",
    "stgpool_capacity": "select est_capacity_mb from stgpools where stgpool_name='{0}'",
    
    # --- MULTI-VALUE CHECKS (JSON Output) ---
    "stgpool_stats": "select pct_utilized, est_capacity_mb from stgpools where stgpool_name='{0}'",
    "scratch_count": "select count(*) from libvolumes where status='Scratch' and library_name='{0}'"
}

def load_config(config_path):
    """Loads credentials and settings from an INI file."""
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    if 'isp' not in config:
        print(f"Error: Section [isp] missing in {config_path}")
        sys.exit(1)
    
    return config['isp']

def run_query(query_key, param, config, server_override=None):
    if query_key not in QUERIES:
        print(f"Error: Query '{query_key}' not defined.")
        sys.exit(1)

    # 1. Prepare SQL
    raw_sql = QUERIES[query_key]
    if "{0}" in raw_sql:
        if not param:
            print(f"Error: Query '{query_key}' requires a parameter.")
            sys.exit(1)
        sql = raw_sql.format(param)
    else:
        sql = raw_sql
    
    # 2. Prepare Variables from Config
    try:
        user = config.get('user')
        password = config.get('password')
        dsmadmc = config.get('dsmadmc', '/usr/bin/dsmadmc')
        # Priority: Command Line Flag > Config File > None
        server = server_override if server_override else config.get('server')
    except Exception as e:
        print(f"Error reading config keys: {e}")
        sys.exit(1)

    if not user or not password:
        print("Error: 'user' and 'password' are required in config file.")
        sys.exit(1)

    # 3. Construct Command
    cmd = [
        dsmadmc, 
        f"-id={user}", 
        f"-pa={password}", 
        "-dataonly=yes", 
        "-comma", 
        "-noc"
    ]
    
    if server:
        cmd.append(f"-se={server}")
        
    cmd.append(sql)

    # 4. Execute
    try:
        # stdout=subprocess.PIPE is used for Python 3.6+ compatibility
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            universal_newlines=True, 
            timeout=15
        )
        
        # Handle ISP Errors
        if "ANS" in result.stdout or result.returncode != 0:
             if "ANR2034E" in result.stdout: # No match found
                 print("0")
                 return
             if "ANS" in result.stdout:
                 print(f"Error: ISP Client failed: {result.stdout.strip()}")
                 sys.exit(1)

        output = result.stdout.strip()
        
        # --- MODE 1: DISCOVERY (JSON) ---
        if query_key.startswith("discovery_"):
            data = []
            if output:
                reader = csv.reader(io.StringIO(output))
                for row in reader:
                    if row and row[0]:
                        macro_suffix = query_key.split("_")[1].upper()
                        data.append({f"{{#{macro_suffix}}}": row[0]})
            print(json.dumps({"data": data}))
            return

        # --- MODE 2: MULTI-VALUE STATS (JSON) ---
        if query_key == "stgpool_stats":
            reader = csv.reader(io.StringIO(output))
            for row in reader:
                if row:
                    stats = {
                        "pct_utilized": float(row[0]) if row[0] else 0.0,
                        "est_capacity_mb": float(row[1]) if len(row) > 1 and row[1] else 0.0
                    }
                    print(json.dumps(stats))
                    return
            print(json.dumps({"pct_utilized": 0, "est_capacity_mb": 0}))
            return

        # --- MODE 3: STANDARD VALUE ---
        if not output:
            print("0")
            return

        reader = csv.reader(io.StringIO(output))
        for row in reader:
            if row:
                print(row[0] if row[0] else "0")
                return

    except subprocess.TimeoutExpired:
        print("Error: Timeout connecting to ISP")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zabbix ISP Monitor")
    parser.add_argument("query", help="The query key (e.g., db_util, discovery_stgpool)")
    parser.add_argument("param", nargs="?", help="Optional parameter for the query (e.g., pool name)")
    parser.add_argument("-s", "--server", help="Override the ISP Server Name (dsm.sys stanza)")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH, help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})")
    
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    run_query(args.query, args.param, cfg, args.server) 