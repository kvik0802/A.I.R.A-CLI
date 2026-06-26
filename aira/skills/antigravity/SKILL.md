# Antigravity SDK

Core SDK for agent orchestration, file operations, and planning utilities.

## Artifact Creation
Create structured files and artifacts for projects:

```python
from pathlib import Path

def write_artifact(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    print(f"Created: {p}")

def write_to_file(path, content, append=False):
    mode = 'a' if append else 'w'
    with open(path, mode) as f:
        f.write(content)

# Standard project artifacts
write_artifact("implementation_plan.md", "# Implementation Plan\n\n## Steps\n1. ...")
write_artifact("walkthrough.md", "# Walkthrough\n\n## Architecture\n...")
```

## Project Planning
```markdown
# implementation_plan.md
## Overview
## Architecture
## Data Flow
## Step-by-Step
## Dependencies
## Testing Strategy
```

## File System Utilities
```python
import shutil, os

def ensure_dir(path): Path(path).mkdir(parents=True, exist_ok=True)
def copy_tree(src, dst): shutil.copytree(src, dst, dirs_exist_ok=True)
def safe_delete(path):
    p = Path(path)
    if p.is_dir(): shutil.rmtree(p)
    else: p.unlink()
```

## Background Tasks
```python
import threading, time

def run_background(name, fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True, name=name)
    t.start()
    return t
```
