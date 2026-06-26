"""
AIRA Skill Plugin System
------------------------
Loads file-based skills from aira/skills/<plugin>/ directories.
Each plugin is a directory with:
  plugin.json   - metadata
  skills/       - subdirectory of SKILL.md files (optional)
  SKILL.md      - single skill file (alternative to skills/ dir)
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

SKILLS_DIR = Path(__file__).parent

_loaded_skills = []
_loaded_plugins = {}


def _load_plugin(plugin_dir: Path) -> Optional[dict]:
    """Load a single plugin from its directory."""
    pf = plugin_dir / "plugin.json"
    if not pf.exists():
        return None
    try:
        meta = json.loads(pf.read_text(encoding="utf-8"))
    except Exception:
        meta = {"name": plugin_dir.name, "description": plugin_dir.name}

    skills = []

    # Single SKILL.md at plugin root (like antigravity)
    root_skill = plugin_dir / "SKILL.md"
    if root_skill.exists():
        skills.append({
            "name": meta.get("name", plugin_dir.name),
            "content": root_skill.read_text(encoding="utf-8"),
            "source": str(root_skill),
        })

    # Multiple skills in skills/ subdir
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for sk_file in sorted(skills_dir.glob("**/SKILL.md")):
            # Extract skill name from parent directory name
            skill_name = sk_file.parent.name
            skills.append({
                "name": skill_name,
                "content": sk_file.read_text(encoding="utf-8"),
                "source": str(sk_file),
            })

    return {
        "name": meta.get("name", plugin_dir.name),
        "description": meta.get("description", ""),
        "version": meta.get("version", "1.0.0"),
        "path": str(plugin_dir),
        "skills": skills,
    }


def reload_skills():
    """Scan skills/ directory and load all plugins + skills."""
    global _loaded_plugins, _loaded_skills
    _loaded_plugins = {}
    _loaded_skills = []

    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        plugin = _load_plugin(entry)
        if plugin:
            _loaded_plugins[plugin["name"]] = plugin
            _loaded_skills.extend(plugin["skills"])

    return _loaded_plugins


def get_loaded_plugins() -> dict:
    if not _loaded_plugins:
        reload_skills()
    return _loaded_plugins


def get_loaded_skills() -> list:
    if not _loaded_skills:
        reload_skills()
    return _loaded_skills


def get_plugin(name: str) -> Optional[dict]:
    plugins = get_loaded_plugins()
    # Try exact match first, then case-insensitive
    if name in plugins:
        return plugins[name]
    for k, v in plugins.items():
        if k.lower() == name.lower():
            return v
    return None


def get_skill(name: str) -> Optional[dict]:
    skills = get_loaded_skills()
    for s in skills:
        if s["name"] == name:
            return s
    for s in skills:
        if name.lower() in s["name"].lower():
            return s
    return None


def search_skills(query: str) -> List[dict]:
    q = query.lower()
    results = []
    for s in get_loaded_skills():
        if q in s["name"].lower() or q in s["content"][:200].lower():
            results.append(s)
    return results


def build_skill_context(max_skills: int = 5) -> str:
    """Build a context string from loaded skills for injection into system prompt."""
    skills = get_loaded_skills()
    if not skills:
        return ""

    parts = ["\n\nAVAILABLE SKILL PLUGINS:"]
    for i, s in enumerate(skills[:max_skills]):
        # Extract a concise description from the first few lines
        lines = s["content"].splitlines()
        desc = ""
        for line in lines:
            stripped = line.strip().strip("#* ")
            if stripped and not stripped.startswith("---") and not stripped.startswith("name:"):
                desc = stripped[:120]
                break
        parts.append(f"  \u2022 {s['name']}: {desc}")
    parts.append(f"  ({len(skills)} skills loaded from {len(get_loaded_plugins())} plugins)")

    return "\n".join(parts)


def build_skill_system_block(plugin_names: List[str] = None) -> str:
    """Build a full skill block for specific plugins to inject into system prompt."""
    if plugin_names:
        plugins = [get_plugin(n) for n in plugin_names]
        plugins = [p for p in plugins if p]
    else:
        plugins = list(get_loaded_plugins().values())

    if not plugins:
        return ""

    blocks = []
    for plugin in plugins:
        blocks.append(f"=== Plugin: {plugin['name']} ===")
        if plugin["description"]:
            blocks.append(plugin["description"])
        for skill in plugin["skills"][:3]:  # Max 3 per plugin to avoid bloat
            lines = skill["content"].splitlines()
            # Extract name from YAML frontmatter
            name = skill["name"]
            for line in lines[:20]:
                if line.startswith("description:"):
                    desc = line[12:].strip().strip(">- '\"")
                    blocks.append(f"  \u2022 {name}: {desc[:150]}")
                    break
            else:
                blocks.append(f"  \u2022 {name}")

    return "\n".join(blocks)


# Auto-load on import
reload_skills()
