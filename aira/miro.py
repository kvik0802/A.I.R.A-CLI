import json
from pathlib import Path
from datetime import datetime

AIRA_HOME = Path.home() / ".aira"
MIRO_FILE = AIRA_HOME / "miro.json"


def _load() -> dict:
    if MIRO_FILE.exists():
        try:
            return json.loads(MIRO_FILE.read_text())
        except Exception:
            pass
    return {"projects": {}, "tasks": {}, "deps": []}


def _save(data: dict):
    AIRA_HOME.mkdir(exist_ok=True)
    MIRO_FILE.write_text(json.dumps(data, indent=2))


def miro_list_projects() -> list[dict]:
    data = _load()
    return [
        {"name": k, "task_count": len(v.get("tasks", [])), "desc": v.get("desc", "")}
        for k, v in data["projects"].items()
    ]


def miro_create_project(name: str, desc: str = "") -> dict:
    data = _load()
    if name in data["projects"]:
        return {"success": False, "error": f"Project '{name}' exists"}
    data["projects"][name] = {"desc": desc, "tasks": [], "created": datetime.now().isoformat()}
    _save(data)
    return {"success": True, "name": name}


def miro_delete_project(name: str) -> dict:
    data = _load()
    if name not in data["projects"]:
        return {"success": False, "error": f"Project '{name}' not found"}
    task_ids = set(data["projects"][name].get("tasks", []))
    data["deps"] = [d for d in data["deps"] if d[0] not in task_ids and d[1] not in task_ids]
    for tid in task_ids:
        data["tasks"].pop(tid, None)
    del data["projects"][name]
    _save(data)
    return {"success": True}


def miro_add_task(project: str, title: str, desc: str = "") -> dict:
    data = _load()
    if project not in data["projects"]:
        return {"success": False, "error": f"Project '{project}' not found"}
    tid = f"{project}-{len(data['tasks']) + 1}"
    data["tasks"][tid] = {
        "title": title, "desc": desc, "status": "todo",
        "project": project, "created": datetime.now().isoformat()
    }
    data["projects"][project]["tasks"].append(tid)
    _save(data)
    return {"success": True, "id": tid}


def miro_update_task(task_id: str, **kwargs) -> dict:
    data = _load()
    if task_id not in data["tasks"]:
        return {"success": False, "error": f"Task '{task_id}' not found"}
    for k, v in kwargs.items():
        if v is not None:
            data["tasks"][task_id][k] = v
    _save(data)
    return {"success": True}


def miro_move(task_id: str, status: str) -> dict:
    if status not in ("todo", "doing", "done"):
        return {"success": False, "error": "Status must be: todo, doing, done"}
    return miro_update_task(task_id, status=status)


def miro_add_dep(task_id: str, depends_on: str) -> dict:
    data = _load()
    if task_id not in data["tasks"]:
        return {"success": False, "error": f"Task '{task_id}' not found"}
    if depends_on not in data["tasks"]:
        return {"success": False, "error": f"Task '{depends_on}' not found"}
    if task_id == depends_on:
        return {"success": False, "error": "Task cannot depend on itself"}
    if [task_id, depends_on] in data["deps"]:
        return {"success": False, "error": "Dependency already exists"}
    data["deps"].append([task_id, depends_on])
    _save(data)
    return {"success": True}


def miro_get_board(project: str) -> dict | None:
    data = _load()
    if project not in data["projects"]:
        return None
    proj = data["projects"][project]
    columns = {"todo": [], "doing": [], "done": []}
    for tid in proj.get("tasks", []):
        t = data["tasks"].get(tid)
        if t:
            deps = [d[1] for d in data["deps"] if d[0] == tid]
            blockers = [data["tasks"].get(d, {}).get("title", d) for d in deps]
            entry = {**t, "id": tid, "blocked_by": blockers if blockers else None}
            columns.get(t["status"], columns["todo"]).append(entry)
    return {"name": project, "desc": proj.get("desc", ""), "columns": columns}


def miro_decompose(project: str, goal: str, steps: list[str]) -> dict:
    data = _load()
    if project not in data["projects"]:
        miro_create_project(project, f"Decomposed from: {goal}")
    created = []
    for i, step in enumerate(steps):
        r = miro_add_task(project, step)
        if r["success"]:
            created.append(r["id"])
            if i > 0:
                miro_add_dep(r["id"], created[i - 1])
    return {"success": True, "project": project, "tasks": created}
