import sys
with open('C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/task.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('- [ ] Detect OS via SSH in `ssh_utils.py`', '- [x] Detect OS via SSH in `ssh_utils.py`')
text = text.replace('- [ ] Implement Windows performance and log collection via WMI/PowerShell', '- [x] Implement Windows performance and log collection via WMI/PowerShell')
text = text.replace('- [ ] Add generic CPU/RAM OIDs in `snmp_utils.py`', '- [x] Add generic CPU/RAM OIDs in `snmp_utils.py`')
text = text.replace('- [ ] Adjust `smart_monitor.py` to handle Windows and generic network devices gracefully', '- [x] Adjust `smart_monitor.py` to handle Windows and generic network devices gracefully')

with open('C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/task.md', 'w', encoding='utf-8') as f:
    f.write(text)
