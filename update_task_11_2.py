import sys
path = 'C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/task.md'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if '[ ] Add detailed Windows metrics (Disk I/O, Network I/O, Drops/Errors) in `ssh_utils.py`' in line:
        new_lines.append(line.replace('[ ]', '[x]'))
    elif '[ ] Refactor `commande_reseau.py` to support OS-specific commands (ping, traceroute, netstat)' in line:
        new_lines.append(line.replace('[ ]', '[x]'))
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
