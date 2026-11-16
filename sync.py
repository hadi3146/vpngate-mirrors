#!/usr/bin/env python3
"""
Automated VPN Gate Mirror Synchronizer
Fetches the live public VPN Gate CSV directory, validates, prioritizes European
and low-latency SoftEther SSTP-capable nodes, and saves a clean servers.csv.
"""

import sys
import os
import urllib.request
import base64
import re

MIRROR_URLS = [
    "https://www.vpngate.net/api/iphone/",
    "http://www.vpngate.net/api/iphone/",
    "http://vpngate.opengw.net/api/iphone/",
    "http://219.100.37.121/api/iphone/",
]

EUROPEAN_COUNTRIES = {
    "RO", "DE", "NL", "FR", "GB", "UK", "IT", "ES", "PL", "SE", "FI", "NO", "DK",
    "CH", "AT", "BE", "CZ", "HU", "BG", "GR", "PT", "IE", "UA", "MD", "RS", "HR",
    "SK", "SI", "LT", "LV", "EE", "LU", "IS", "TR", "AE"
}

CENSORED_COUNTRIES = {"RU", "IR", "CN", "BY", "SY", "CU", "KP"}

def fetch_raw_csv() -> str:
    for url in MIRROR_URLS:
        try:
            print(f"Fetching from {url}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                text = data.decode("utf-8", errors="replace")
                if "*vpn_servers" in text or "#HostName" in text:
                    print(f"Successfully fetched {len(data)} bytes from {url}")
                    return text
        except Exception as e:
            print(f"Failed {url}: {e}")
    raise RuntimeError("All VPN Gate mirrors failed to respond.")

def parse_and_optimize(csv_text: str) -> str:
    lines = csv_text.strip().splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("#HostName") or line.startswith("HostName"):
            header_idx = i
            break
            
    if header_idx == -1:
        raise ValueError("Invalid CSV: header row not found.")
        
    header_line = lines[header_idx]
    data_lines = [l for l in lines[header_idx + 1:] if l.strip() and not l.startswith("*")]
    
    parsed_rows = []
    for line in data_lines:
        parts = line.split(",")
        if len(parts) < 15:
            continue
        hostname = parts[0].strip()
        ip = parts[1].strip()
        try:
            score = int(parts[2].strip())
            ping = int(parts[3].strip())
            speed = int(parts[4].strip())
        except ValueError:
            continue
            
        country_long = parts[5].strip()
        country_short = parts[6].strip().upper()
        
        # Skip blacklisted / academic blackhole / censored exit nodes
        if ip.startswith("219.100.37.") or country_short in CENSORED_COUNTRIES:
            continue
            
        is_eu = country_short in EUROPEAN_COUNTRIES
        parsed_rows.append({
            "line": line,
            "hostname": hostname,
            "ip": ip,
            "score": score,
            "ping": ping,
            "speed": speed,
            "country_short": country_short,
            "is_eu": is_eu
        })
        
    # Sort: European / low-latency regions first, then high speed, then ping
    parsed_rows.sort(key=lambda r: (
        not r["is_eu"],
        -r["speed"],
        r["ping"] if r["ping"] > 0 else 99999,
        -r["score"]
    ))
    
    output_lines = [
        "*vpn_servers",
        header_line
    ]
    for r in parsed_rows:
        output_lines.append(r["line"])
    output_lines.append("*")
    
    print(f"Optimized {len(parsed_rows)} active servers (European/Low-Latency: {sum(1 for r in parsed_rows if r['is_eu'])}).")
    return "\n".join(output_lines) + "\n"

def main():
    try:
        raw = fetch_raw_csv()
        optimized = parse_and_optimize(raw)
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servers.csv")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(optimized)
        print(f"Saved optimized directory to {out_path} ({os.path.getsize(out_path)} bytes).")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

