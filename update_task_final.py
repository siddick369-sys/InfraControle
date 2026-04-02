import sys
path = 'C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/task.md'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if '[ ]' in line and (
        'Detect OS' in line or 
        'Implement Windows performance' in line or 
        'Add generic CPU/RAM OIDs' in line or
        'Adjust `smart_monitor.py`' in line
    ):
        new_lines.append(line.replace('[ ]', '[x]'))
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
