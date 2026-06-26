import os
import json
import re
from typing import Optional, Any
from abc import ABC, abstractmethod

import anthropic
import requests
from aira.memory import (
    save_memory, search_memory, save_skill, get_skill,
    list_skills, update_skill_success
)


# ── Token Tracking ─────────────────────────────────────────────────────────────

_session_usage = {"prompt": 0, "completion": 0, "cached": 0}

COST_PER_1M = {
    "claude-sonnet-4-6": (3, 15), "claude-sonnet-4-6-": (3, 15),
    "claude-sonnet-4": (3, 15), "claude-3-opus": (15, 75),
    "claude-3.5-sonnet": (3, 15), "claude-3.5-haiku": (0.8, 4),
    "claude-3-haiku": (0.25, 1.25), "gpt-4o": (5, 15), "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-turbo": (10, 30), "gemini-2.0-flash": (0.1, 0.4),
    "gemini-2.5-pro": (1.25, 5), "deepseek-chat": (0.5, 2),
    "deepseek-reasoner": (0.5, 2), "mistral-large-latest": (2, 6),
    "command-r-plus": (3, 15), "llama3-70b-8192": (0.5, 0.8),
}


def record_usage(prompt: int, completion: int, cached: int = 0):
    global _session_usage
    _session_usage["prompt"] += prompt
    _session_usage["completion"] += completion
    _session_usage["cached"] += cached


def get_usage() -> dict:
    return dict(_session_usage)


def reset_usage():
    global _session_usage
    _session_usage = {"prompt": 0, "completion": 0, "cached": 0}


def estimate_cost(model: str, prompt: int, completion: int) -> float:
    prices = COST_PER_1M.get(model, (2, 8))
    return (prompt / 1_000_000 * prices[0]) + (completion / 1_000_000 * prices[1])


# ── Abstract Provider ─────────────────────────────────────────────────────────

class AIProvider(ABC):
    @abstractmethod
    def __init__(self, api_key: str, model: str):
        ...

    @abstractmethod
    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        ...


# ── Anthropic ─────────────────────────────────────────────────────────────────

class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        )
        record_usage(response.usage.input_tokens, response.usage.output_tokens)
        return response.content[0].text


# ── OpenAI ────────────────────────────────────────────────────────────────────

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.model = model
        from openai import OpenAI as _OpenAI
        self.client = _OpenAI(api_key=api_key)

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=formatted
        )
        if response.usage:
            record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return response.choices[0].message.content or ""


# ── OpenRouter ───────────────────────────────────────────────────────────────

class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        self.model = model
        from openai import OpenAI as _OpenAI
        self.client = _OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=formatted
            )
            if response.usage:
                record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                raise Exception(f"Rate limit error: {error_msg}")
            raise


# ── Gemini ────────────────────────────────────────────────────────────────────

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.model = model
        self.api_key = api_key
        import google.generativeai as genai
        genai.configure(api_key=api_key)

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        import google.generativeai as genai

        generation_config = {"max_output_tokens": max_tokens}
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system or None,
            generation_config=generation_config
        )

        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})

        last_msg = messages[-1]["content"] if messages else ""

        if history:
            chat = model.start_chat(history=history)
            response = chat.send_message(last_msg)
        else:
            response = model.generate_content(last_msg)

        try:
            meta = response.usage_metadata
            record_usage(meta.prompt_token_count, meta.candidates_token_count)
        except Exception:
            pass
        return response.text


# ── Groq ──────────────────────────────────────────────────────────────────────

class GroqProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "llama3-70b-8192"):
        self.model = model
        from openai import OpenAI as _OpenAI
        self.client = _OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=formatted
        )
        if response.usage:
            record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return response.choices[0].message.content or ""


# ── DeepSeek ──────────────────────────────────────────────────────────────────

class DeepSeekProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.model = model
        from openai import OpenAI as _OpenAI
        self.client = _OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=formatted
        )
        if response.usage:
            record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return response.choices[0].message.content or ""


# ── Mistral ───────────────────────────────────────────────────────────────────

class MistralProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        self.model = model
        from openai import OpenAI as _OpenAI
        self.client = _OpenAI(
            api_key=api_key,
            base_url="https://api.mistral.ai/v1"
        )

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=formatted
        )
        if response.usage:
            record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return response.choices[0].message.content or ""


# ── Cohere ────────────────────────────────────────────────────────────────────

class CohereProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "command-r-plus"):
        self.model = model
        self.api_key = api_key

    def create_message(self, *, system: str, messages: list, max_tokens: int = 2048) -> str:
        import cohere
        client = cohere.Client(api_key=self.api_key)

        chat_history = []
        for m in messages[:-1]:
            chat_history.append({
                "role": m["role"],
                "message": m["content"]
            })

        response = client.chat(
            model=self.model,
            message=messages[-1]["content"] if messages else "",
            chat_history=chat_history or None,
            preamble=system or None,
            max_tokens=max_tokens
        )
        try:
            meta = response.meta.billed_units
            record_usage(meta.input_tokens, meta.output_tokens)
        except Exception:
            pass
        return response.text


# ── Provider Registry ─────────────────────────────────────────────────────────

PROVIDER_REGISTRY = {
    "anthropic":   {"class": AnthropicProvider,   "default_model": "claude-sonnet-4-6"},
    "openai":      {"class": OpenAIProvider,      "default_model": "gpt-4o"},
    "openrouter":  {"class": OpenRouterProvider,  "default_model": "anthropic/claude-3.5-sonnet"},
    "gemini":      {"class": GeminiProvider,      "default_model": "gemini-2.0-flash"},
    "groq":        {"class": GroqProvider,        "default_model": "llama3-70b-8192"},
    "deepseek":    {"class": DeepSeekProvider,    "default_model": "deepseek-chat"},
    "mistral":     {"class": MistralProvider,     "default_model": "mistral-large-latest"},
    "cohere":      {"class": CohereProvider,      "default_model": "command-r-plus"},
}

PROVIDER_HELP = {
    "anthropic":   "sk-ant-...",
    "openai":      "sk-proj-...",
    "openrouter":  "sk-or-...",
    "gemini":      "AIza...",
    "groq":        "gsk_...",
    "deepseek":    "sk-...",
    "mistral":     "...",
    "cohere":      "...",
}

PROVIDER_MODELS = {
    "anthropic": [
        {"id": "claude-sonnet-4-6",        "name": "Claude Sonnet 4.6",      "tier": "paid", "desc": "Best balance of speed & quality"},
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4",        "tier": "paid", "desc": "Latest Sonnet release"},
        {"id": "claude-3-5-haiku-20241022","name": "Claude 3.5 Haiku",       "tier": "paid", "desc": "Fast & affordable"},
        {"id": "claude-3-opus-20240229",   "name": "Claude 3 Opus",          "tier": "paid", "desc": "Most powerful (slowest)"},
    ],
    "openai": [
        {"id": "gpt-4o",                   "name": "GPT-4o",                 "tier": "paid", "desc": "Latest multimodal flagship"},
        {"id": "gpt-4o-mini",              "name": "GPT-4o Mini",            "tier": "paid", "desc": "Affordable & fast"},
        {"id": "gpt-4-turbo",              "name": "GPT-4 Turbo",            "tier": "paid", "desc": "High quality, slower"},
        {"id": "gpt-3.5-turbo",            "name": "GPT-3.5 Turbo",          "tier": "paid", "desc": "Legacy, efficient"},
    ],
    "openrouter": [
        {"id": "openai/gpt-4o",            "name": "OpenAI GPT-4o",          "tier": "paid", "desc": "Via OpenRouter"},
        {"id": "anthropic/claude-3.5-sonnet","name": "Claude 3.5 Sonnet",    "tier": "paid", "desc": "Via OpenRouter"},
        {"id": "meta-llama/llama-3-70b-instruct","name": "Llama 3 70B",     "tier": "free", "desc": "Free tier available"},
        {"id": "meta-llama/llama-3-8b-instruct","name": "Llama 3 8B",       "tier": "free", "desc": "Free, lightweight"},
        {"id": "mistralai/mistral-7b-instruct","name": "Mistral 7B",         "tier": "free", "desc": "Free tier"},
        {"id": "google/gemma-2-27b-it",    "name": "Gemma 2 27B",            "tier": "free", "desc": "Free tier"},
    ],
    "gemini": [
        {"id": "gemini-2.0-flash",         "name": "Gemini 2.0 Flash",       "tier": "free", "desc": "Fast, free quota"},
        {"id": "gemini-2.0-flash-lite",    "name": "Gemini 2.0 Flash Lite",  "tier": "free", "desc": "Lightweight, free"},
        {"id": "gemini-1.5-pro",           "name": "Gemini 1.5 Pro",         "tier": "paid", "desc": "Most capable"},
        {"id": "gemini-1.5-flash",         "name": "Gemini 1.5 Flash",       "tier": "free", "desc": "Fast, free quota"},
    ],
    "groq": [
        {"id": "llama3-70b-8192",          "name": "Llama 3 70B",            "tier": "free", "desc": "Free, 8K context"},
        {"id": "llama3-8b-8192",           "name": "Llama 3 8B",             "tier": "free", "desc": "Free, fast"},
        {"id": "mixtral-8x7b-32768",       "name": "Mixtral 8x7B",           "tier": "free", "desc": "Free, 32K context"},
        {"id": "gemma2-9b-it",             "name": "Gemma 2 9B",             "tier": "free", "desc": "Free"},
        {"id": "gemma-7b-it",              "name": "Gemma 7B",               "tier": "free", "desc": "Free"},
    ],
    "deepseek": [
        {"id": "deepseek-chat",            "name": "DeepSeek Chat",          "tier": "paid", "desc": "General purpose"},
        {"id": "deepseek-coder",           "name": "DeepSeek Coder",         "tier": "paid", "desc": "Code specialized"},
    ],
    "mistral": [
        {"id": "mistral-large-latest",     "name": "Mistral Large",          "tier": "paid", "desc": "Latest flagship"},
        {"id": "mistral-medium-latest",    "name": "Mistral Medium",         "tier": "paid", "desc": "Balanced"},
        {"id": "mistral-small-latest",     "name": "Mistral Small",          "tier": "paid", "desc": "Fast & affordable"},
        {"id": "open-mistral-nemo",        "name": "Mistral Nemo",           "tier": "free", "desc": "Free tier"},
    ],
    "cohere": [
        {"id": "command-r-plus",           "name": "Command R+",             "tier": "paid", "desc": "Most powerful"},
        {"id": "command-r",                "name": "Command R",              "tier": "paid", "desc": "Balanced"},
        {"id": "command-light",            "name": "Command Light",          "tier": "free", "desc": "Lightweight, free"},
    ],
}

PROVIDER_NAMES = list(PROVIDER_REGISTRY.keys())

current_provider_instance: Optional[AIProvider] = None
current_provider_name: str = "anthropic"
current_model: str = "claude-sonnet-4-6"
_current_api_key: str = ""

# ── Multi-Model Routing ──────────────────────────────────────────────────────
# Map task types to (provider, model). Falls back to defaults if not set.

TASK_ROUTES = {}  # {"reasoning": ("anthropic", "claude-sonnet-4-6"), "code": ("openai", "gpt-4o"), ...}


def set_task_route(task_type: str, provider: str, model: str):
    TASK_ROUTES[task_type] = (provider, model)


def get_task_route(task_type: str) -> tuple:
    """Return (provider, model) for a task type, falling back to defaults."""
    route = TASK_ROUTES.get(task_type)
    if route:
        return route
    return (current_provider_name, current_model)


def get_routed_provider(task_type: str, api_key: str = None) -> Optional[AIProvider]:
    """Get a provider instance routed for a specific task type."""
    prov, model = get_task_route(task_type)
    reg = PROVIDER_REGISTRY.get(prov)
    if not reg:
        return None
    key = api_key or _current_api_key
    return reg["class"](api_key=key, model=model)


# ── Model Fetcher ─────────────────────────────────────────────────────────────

def fetch_models(provider: str, api_key: str) -> list:
    """Fetch available models from the provider's API. Falls back to hardcoded list on failure."""
    fetcher = _MODEL_FETCHERS.get(provider)
    if fetcher:
        try:
            models = fetcher(api_key)
            if models:
                return models
        except Exception:
            pass
    return PROVIDER_MODELS.get(provider, [])


def _fetch_openai_models(api_key: str) -> list:
    r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data.get("data", []):
        mid = m["id"]
        # Filter out non-chat models
        if "gpt" in mid or "o1" in mid or "o3" in mid:
            models.append({"id": mid, "name": mid, "tier": "paid", "desc": ""})
    return sorted(models, key=lambda x: x["id"])


def _fetch_openrouter_models(api_key: str) -> list:
    r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        prompt_cost = float(pricing.get("prompt", 1))
        completion_cost = float(pricing.get("completion", 1))
        is_free = prompt_cost == 0 and completion_cost == 0
        models.append({
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "tier": "free" if is_free else "paid",
            "desc": (m.get("description", "") or "")[:60]
        })
    return models


def _fetch_gemini_models(api_key: str) -> list:
    r = requests.get(f"https://generativelanguage.googleapis.com/v1/models?key={api_key}", timeout=8)
    data = r.json()
    models = []
    for m in data.get("models", []):
        mid = m["name"].replace("models/", "")
        display = m.get("displayName", mid)
        supported = m.get("supportedGenerationMethods", [])
        if "generateContent" not in supported:
            continue
        # Flash & gemma models have free tier
        is_free = any(tag in mid.lower() for tag in ["flash", "gemma", "lite"])
        models.append({
            "id": mid,
            "name": display,
            "tier": "free" if is_free else "paid",
            "desc": (m.get("description", "") or "")[:60]
        })
    return models


def _fetch_groq_models(api_key: str) -> list:
    r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data.get("data", []):
        mid = m["id"]
        models.append({
            "id": mid,
            "name": mid,
            "tier": "free",
            "desc": ""
        })
    return sorted(models, key=lambda x: x["id"])


def _fetch_deepseek_models(api_key: str) -> list:
    r = requests.get("https://api.deepseek.com/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data.get("data", []):
        mid = m["id"]
        models.append({
            "id": mid,
            "name": mid,
            "tier": "paid",
            "desc": ""
        })
    return models


def _fetch_mistral_models(api_key: str) -> list:
    r = requests.get("https://api.mistral.ai/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data:
        mid = m["id"]
        is_free = "open-" in mid or "tiny" in mid
        models.append({
            "id": mid,
            "name": m.get("name", m.get("id", "")),
            "tier": "free" if is_free else "paid",
            "desc": ""
        })
    return models


def _fetch_cohere_models(api_key: str) -> list:
    r = requests.get("https://api.cohere.ai/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    data = r.json()
    models = []
    for m in data:
        pricing = m.get("pricing", {})
        tier = pricing.get("tier", "").lower()
        is_free = tier in ("free", "community", "hobby")
        mid = m["id"]
        models.append({
            "id": mid,
            "name": m.get("name", mid),
            "tier": "free" if is_free else "paid",
            "desc": (m.get("description", "") or "")[:60]
        })
    return models


_MODEL_FETCHERS = {
    "openai":     _fetch_openai_models,
    "openrouter": _fetch_openrouter_models,
    "gemini":     _fetch_gemini_models,
    "groq":       _fetch_groq_models,
    "deepseek":   _fetch_deepseek_models,
    "mistral":    _fetch_mistral_models,
    "cohere":     _fetch_cohere_models,
}


# ── Initialization ────────────────────────────────────────────────────────────

def init_client(api_key: str, provider: str = "anthropic", model: str = None):
    global current_provider_instance, current_provider_name, current_model, _current_api_key
    current_provider_name = provider
    _current_api_key = api_key
    if provider in PROVIDER_REGISTRY:
        info = PROVIDER_REGISTRY[provider]
        current_model = model or info["default_model"]
        current_provider_instance = info["class"](api_key=api_key, model=current_model)
    else:
        raise ValueError(f"Unknown AI provider: {provider}. Supported: {', '.join(PROVIDER_NAMES)}")


# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are AIRA, a terminal AI agent. Be concise and direct.

Capabilities (use only when needed):
<CMD>shell command</CMD>
<MEMORY priority="1-3" project="name" tags="tag1,tag2">content</MEMORY>
<SKILL name="name" description="what it does">step1||step2||step3</SKILL>
<SUBAGENT task="description">context</SUBAGENT>
<AGENT_CHAIN>agent1,agent2,agent3</AGENT_CHAIN>
<WEB_SEARCH>query</WEB_SEARCH>
<SCHEDULE cron="* * * * *" task="description"/>

NEVER ASK QUESTIONS. Always execute immediately with the information given. Make reasonable assumptions if details are missing.

IMPORTANT: Respond naturally to conversational input (greetings, questions, chat). Only output code when the user explicitly requests code (e.g., "write a function", "show me python code", "create a script").

For explicit code requests:
- Provide the code directly in your response WITHOUT using <CMD> tags
- Keep it simple and correct
- Only use <CMD> when you need to actually execute/run code or create files

MULTI-AGENT COLLABORATION:
For complex tasks (websites, apps, full projects), use <AGENT_CHAIN> to run multiple agents in parallel:
- webdev, coder, security (for web projects - all work simultaneously)
- planner, webdev, coder (for complex builds - all work simultaneously)
- researcher, writer (for content projects - all work simultaneously)
- data, planner, coder (for data projects - all work simultaneously)
Available agents: coder, researcher, sysadmin, webdev, writer, data, security, planner

Example: <AGENT_CHAIN>webdev,coder,security</AGENT_CHAIN> will:
- Run webdev, coder, and security ALL AT THE SAME TIME
- Each agent processes the request independently with their specialized perspective
- All results are collected and directives executed together

CRITICAL - Windows commands (user is on Windows):
- Use `mkdir` to create directories (NOT `touch` - that doesn't exist on Windows)
- Use `echo text > file` to write files (use parentheses for multi-line: (echo line1 && echo line2) > file)
- Use `type nul > file` to create empty files
- Use absolute paths like C:\\Users\\vicky\\Desktop\\filename (not relative paths like Desktop/)
- DO NOT use `cd` commands - the working directory is handled automatically
- Use `&&` to chain commands: `mkdir C:\\Users\\vicky\\Desktop\\myapp && echo hi > C:\\Users\\vicky\\Desktop\\myapp\\index.js`
- Directory listing: use `dir` (NOT `ls`). `dir /s` for recursive, `dir /b` for bare format, `dir /ad` for directories only. Do NOT combine flags like `/sd` - that is invalid.

Always use absolute paths in commands:
✅ <CMD>mkdir C:\\Users\\vicky\\Desktop\\myapp && echo hi > C:\\Users\\vicky\\Desktop\\myapp\\index.js</CMD>
❌ <CMD>cd myapp</CMD> (cd is not needed - use absolute paths)

When building projects: create ALL files with complete working code in one command chain using absolute paths. Then tell the user how to run it.

You are knowledgeable in 100+ programming languages including:
ABAP, ActionScript, Ada, Algol, APL, AppleScript, Assembly, AutoIt, Awk, Bash, BASIC, BCPL, Befunge, Brainfuck, C, C++, C#, Caml, Ceylon, CHILL, Cilk, Clean, Clipper, Clojure, COBOL, CoffeeScript, Crystal, D, Dart, Delphi, Dylan, Eiffel, Elixir, Elm, Emacs Lisp, Erlang, F#, Factor, Falcon, Fantom, Flix, FORTH, Fortran, FoxPro, GAMS, G-code, GLSL, Go, Gosu, Groovy, Hack, Haskell, Haxe, Icon, IDL, Idris, Io, J, Java, JavaScript, JScript, Julia, Kotlin, LabVIEW, Lisp, LiveScript, Logo, Lua, Malbolge, MATLAB, Mercury, ML, Modula-2, Mojo, MQL4, MUMPS, Nim, Nix, Oberon, Object Pascal, Objective-C, OCaml, Opa, OpenCL, Oz, Pascal, Perl, PHP, Pike, PL/I, PL/SQL, PostScript, Prolog, PureScript, Python, Q, Q#, R, Racket, Raku, REBOL, Rexx, Ring, RPG, Ruby, Rust, SAS, Scala, Scheme, Scratch, Sed, Self, Solidity, SPARK, SQL, Squeak, Standard ML, Stata, Swift, Tcl, TypeScript, V, Vala, VBScript, Verilog, VHDL, Visual Basic, WebAssembly, Whitespaces, Wolfram, XQuery, Zig.
"""


# ── AI Response ───────────────────────────────────────────────────────────────

def get_ai_response(messages: list, context_memories: list = None, current_project: str = "AIRA", custom_system: str = None) -> str:
    if not current_provider_instance:
        return f"[ERROR] AIRA brain not initialized. Run: aira setup"

    memory_context = ""
    if context_memories:
        memory_context = "\n\nRELEVANT MEMORIES:\n" + "\n".join(
            f"  [{m['project']}] {m['content']}" for m in context_memories[:5]
        )

    skill_list = list_skills()
    skill_context = ""
    if skill_list:
        skill_context = "\n\nAVAILABLE SKILLS:\n" + "\n".join(
            f"  \u2022 {s['name']}: {s['description']} (used {s['use_count']}x, {s['success_rate']*100:.0f}% success)"
            for s in skill_list[:8]
        )

    # Load file-based skill plugins
    try:
        from aira.skills import build_skill_context as build_skill_plugin_context
        skill_plugin_context = build_skill_plugin_context(max_skills=8)
    except Exception:
        skill_plugin_context = ""

    # Use custom system prompt if provided, otherwise use default
    if custom_system:
        system = custom_system + memory_context + skill_context + skill_plugin_context
    else:
        system = SYSTEM_PROMPT + memory_context + skill_context + skill_plugin_context

    if current_project != "AIRA":
        system += f"\n\nACTIVE PROJECT: {current_project}"

    return current_provider_instance.create_message(
        system=system,
        messages=messages,
        max_tokens=2048
    )


# ── Directive Parsing ─────────────────────────────────────────────────────────

def parse_ai_directives(response_text: str) -> dict:
    directives = {
        "commands": [],
        "memories": [],
        "skills": [],
        "subagents": [],
        "agent_chains": [],
        "web_searches": [],
        "schedules": [],
        "clean_text": response_text
    }

    cmds = re.findall(r'<CMD>(.*?)</CMD>', response_text, re.DOTALL)
    directives["commands"] = [c.strip() for c in cmds]

    memories = re.findall(
        r'<MEMORY(?:\s+priority="(\d+)")?(?:\s+project="([^"]*)")?(?:\s+tags="([^"]*)")?>(.+?)</MEMORY>',
        response_text, re.DOTALL
    )
    for m in memories:
        directives["memories"].append({
            "priority": int(m[0]) if m[0] else 1,
            "project": m[1] or "AIRA",
            "tags": m[2].split(",") if m[2] else [],
            "content": m[3].strip()
        })

    skills = re.findall(
        r'<SKILL\s+name="([^"]+)"\s+description="([^"]+)">(.+?)</SKILL>',
        response_text, re.DOTALL
    )
    for s in skills:
        directives["skills"].append({
            "name": s[0],
            "description": s[1],
            "steps": [step.strip() for step in s[2].split("||")]
        })

    searches = re.findall(r'<WEB_SEARCH>(.*?)</WEB_SEARCH>', response_text, re.DOTALL)
    directives["web_searches"] = [s.strip() for s in searches]

    subagents = re.findall(
        r'<SUBAGENT\s+task="([^"]+)">(.+?)</SUBAGENT>',
        response_text, re.DOTALL
    )
    for sa in subagents:
        directives["subagents"].append({"task": sa[0], "context": sa[1].strip()})

    agent_chains = re.findall(r'<AGENT_CHAIN>(.*?)</AGENT_CHAIN>', response_text, re.DOTALL)
    for ac in agent_chains:
        agents = [a.strip() for a in ac.split(",") if a.strip()]
        directives["agent_chains"].append(agents)

    schedules = re.findall(
        r'<SCHEDULE\s+cron="([^"]+)"\s+task="([^"]+)"/>',
        response_text
    )
    for sc in schedules:
        directives["schedules"].append({"cron": sc[0], "task": sc[1]})

    clean = re.sub(r'<(CMD|MEMORY|SKILL|SUBAGENT|AGENT_CHAIN|WEB_SEARCH|SCHEDULE)[^>]*>.*?</\1>', '', response_text, flags=re.DOTALL)
    clean = re.sub(r'<SCHEDULE[^/]*/>', '', clean)
    directives["clean_text"] = clean.strip()

    return directives


# ── Subagent ──────────────────────────────────────────────────────────────────

def run_subagent(task: str, context: str, api_key: str = None, provider: str = None) -> str:
    api_key = api_key or _current_api_key
    provider = provider or current_provider_name
    if provider not in PROVIDER_REGISTRY:
        return f"[ERROR] Unknown provider: {provider}"

    sub_provider = PROVIDER_REGISTRY[provider]["class"](api_key=api_key, model=current_model)
    sub_system = f"""You are an AIRA subagent. Your ONLY job: {task}
Context: {context}
Be extremely focused. Return ONLY the result. No preamble."""

    return sub_provider.create_message(
        system=sub_system,
        messages=[{"role": "user", "content": f"Execute task: {task}"}],
        max_tokens=1024
    )


# ── Auto Skill Generation ────────────────────────────────────────────────────

def auto_generate_skill_from_conversation(messages: list, api_key: str = None, provider: str = None) -> Optional[dict]:
    if len(messages) < 4:
        return None

    # First pass: extract command sequences and their results
    cmd_blocks = []
    for m in messages:
        content = m.get("content", "")
        cmds = re.findall(r'<CMD>(.*?)</CMD>', content, re.DOTALL)
        for c in cmds:
            cmd_blocks.append(c.strip())

    api_key = api_key or _current_api_key
    provider = provider or current_provider_name
    if provider not in PROVIDER_REGISTRY:
        return None

    extract_provider = PROVIDER_REGISTRY[provider]["class"](api_key=api_key, model=current_model)

    # Build context: last 8 messages + extracted commands
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}" for m in messages[-6:]
    )
    if cmd_blocks:
        conversation_text += "\n\nEXECUTED COMMANDS:\n" + "\n".join(f"  $ {c}" for c in cmd_blocks[-8:])

    response = extract_provider.create_message(
        system="""Extract a reusable skill from this conversation. Look for:
1. Repeated command sequences that could be automated
2. Successful multi-step workflows
3. Project scaffolding patterns

Respond ONLY with valid JSON:
{"name": "kebab-case-name", "description": "one sentence", "steps": ["step1", "step2", ...]}
If no skill is worth saving, respond with: {"skip": true}""",
        messages=[{"role": "user", "content": f"Conversation:\n{conversation_text}"}],
        max_tokens=512
    )

    try:
        text = response.strip()
        text = re.sub(r'```json|```', '', text).strip()
        data = json.loads(text)
        if data.get("skip"):
            return None
        return data
    except Exception:
        return None


# ── Command Suggestion ───────────────────────────────────────────────────────

def get_command_suggestion(partial: str, context: str = "") -> list:
    if not current_provider_instance or len(partial) < 3:
        return []
    try:
        response = current_provider_instance.create_message(
            system="You suggest AIRA terminal commands. Return ONLY a JSON array of 3 command strings. No explanation.",
            messages=[{"role": "user", "content": f"Partial input: '{partial}'\nContext: {context}\nSuggest 3 completions:"}],
            max_tokens=200
        )
        text = response.strip()
        text = re.sub(r'```json|```', '', text).strip()
        return json.loads(text)[:3]
    except Exception:
        return []


# ── AGENTS ────────────────────────────────────────────────────────────────────

AGENTS = {
    "coder": {
        "name": "Coder",
        "description": "Write, debug, and refactor code in any language",
        "system": "You are a senior software engineer. Write clean, efficient, well-structured code. Include error handling and comments where needed. Output complete files using <CMD>.",
        "icon": "💻",
    },
    "researcher": {
        "name": "Researcher",
        "description": "Research topics and provide detailed summaries",
        "system": "You are a research analyst. Use <WEB_SEARCH> to find information, then synthesize findings into clear summaries with sources.",
        "icon": "🔍",
    },
    "sysadmin": {
        "name": "SysAdmin",
        "description": "Manage system, diagnose issues, optimize performance",
        "system": "You are a system administrator. Diagnose issues using <CMD>, check logs, monitor resources, and suggest or apply fixes.",
        "icon": "⚙",
    },
    "webdev": {
        "name": "Web Developer",
        "description": "Build websites, APIs, and web apps",
        "system": "You are a full-stack web developer. Build complete web projects using <CMD> to write files. Include HTML, CSS, JS, and server code as needed.",
        "icon": "🌐",
    },
    "writer": {
        "name": "Writer",
        "description": "Write, edit, and improve content",
        "system": "You are a professional writer. Craft clear, engaging content. Adapt tone to the audience. Use <CMD> to write files when needed.",
        "icon": "✍",
    },
    "data": {
        "name": "Data Analyst",
        "description": "Analyze data, create visualizations, find insights",
        "system": "You are a data analyst. Process data using Python, create charts, and explain findings clearly. Use <CMD> for analysis scripts.",
        "icon": "📊",
    },
    "security": {
        "name": "Security Auditor",
        "description": "Audit system security, check vulnerabilities",
        "system": "You are a security auditor. Check for common vulnerabilities, review permissions, open ports, and suggest hardening measures using <CMD>.",
        "icon": "🔒",
    },
    "planner": {
        "name": "Planner",
        "description": "Break down complex tasks into step-by-step plans",
        "system": "You are a project planner. Break down complex goals into clear, actionable steps with timelines and dependencies. Be methodical.",
        "icon": "📋",
    },
}

AGENT_NAMES = list(AGENTS.keys())
