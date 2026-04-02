import sys
path = 'C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/walkthrough.md'
with open(path, 'a', encoding='utf-8') as f:
    f.write('''
## Phase 11: Deep Adaptive Metrics & OS-Specific Commands

I have successfully transformed the monitoring engine to deeply analyze target machines while adapting all UI and CLI tools to the target Operating System:

### 1. Advanced Adaptive Metrics Collection
- **Windows Targets**: Implemented live `Get-Counter` sampling to calculate exact Physical Disk I/O (`disk_read_mb`, `disk_write_mb`). Additionally, instantiated `Get-NetAdapterStatistics` to scrape actual network adapter counters (Sent/Received Bytes, Packet Drops, and Errors).
- **Linux Targets**: Upgraded `collecter_performance_linux_ssh` to aggressively parse `/proc/diskstats` and `/proc/net/dev`, recording a 2-second time delta to calculate highly accurate `Mbps` bandwidth and disk `MB/s` I/O.
- The `stat_collector.py` orchestrator now unconditionally collects performance metrics as long as valid SSH credentials exist, rather than relying on an archaic hardcoded string check.

### 2. Universal & OS-Targeted Network Commands
- **Dynamic Equipment UI**: Modded `views.py` (specifically `equipement_detail_view`) to instantly filter the list of `CommandeAutomatique` based on the targeted equipment's OS (`type_equipement`).
- **Database Model Refactor**: Appended an `os_cible` choice field to the `CommandeAutomatique` database model, preventing a user from mistakenly pushing a Linux `ifconfig` onto a Windows machine.
- **Fixture Expansion**: Expanded `commande_reseau.py` to auto-inject ~20 advanced Windows networking scripts (e.g. `tracert`, `ipconfig /flushdns`, `Get-NetAdapter`, firewall management) alongside the massive suite of Linux debugging tools.
''')
