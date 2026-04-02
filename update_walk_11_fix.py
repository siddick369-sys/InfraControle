import sys
path = 'C:/Users/USER/.gemini/antigravity/brain/1a040a8b-1a16-42d7-ad53-bc014f74bd5d/walkthrough.md'
with open(path, 'a', encoding='utf-8') as f:
    f.write('''
### 3. Output Cleaning & SSH Optimization
- **ANSI Strip Utility**: Created a `nettoyer_ansi` function in `core.py` using advanced regex to eliminate terminal control characters (e.g. `[?9001h`, `[2J`) that pollute Windows SSH outputs.
- **Adaptive PTY**: Modified the command execution engine to disable Pseudo-Terminal (PTY) requests for Windows machines while maintaining them for Linux (required for `sudo`). This drastically reduces the "garbage" characters sent by the Windows OpenSSH server.
- **Unified Logic**: Refactored the UI views to use the central `executer_commande_core`, ensuring that manual triggers and automated remediations benefit from the same cleaning post-processing.
''')
