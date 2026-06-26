__version__ = "1.0.0"

from aira.brain import (
    init_client, get_ai_response, parse_ai_directives,
    run_subagent, auto_generate_skill_from_conversation,
    get_command_suggestion, fetch_models,
    PROVIDER_NAMES, PROVIDER_HELP, PROVIDER_MODELS, PROVIDER_REGISTRY,
    AnthropicProvider, OpenAIProvider, OpenRouterProvider,
    GeminiProvider, GroqProvider, DeepSeekProvider,
    MistralProvider, CohereProvider,
    current_provider_name, current_model,
    set_task_route, get_task_route, get_routed_provider, TASK_ROUTES,
    AGENTS, AGENT_NAMES
)
from aira.memory import (
    init_storage, save_memory, search_memory, get_all_memories,
    delete_memory, save_skill, get_skill, list_skills,
    start_session, end_session, get_recent_sessions,
    save_project, list_projects,
    save_custom_agent, get_custom_agent, list_custom_agents, delete_custom_agent,
    add_knowledge_edge, get_linked_memories, graph_search
)
from aira.tools import (
    execute_command, get_system_snapshot, get_network_info,
    web_search, fetch_url, read_file, write_file,
    list_directory, copy_to_clipboard, read_clipboard,
    save_schedule, load_schedules, delete_schedule, toggle_schedule,
    get_scheduler_log, init_scheduler,
    create_snapshot, list_snapshots, restore_snapshot,
    vault_set, vault_get, vault_list, vault_delete,
    gh_check, gh_run, docker_check, docker_run, docker_ps
)
from aira.ui import (
    console, print_banner, print_help,
    print_system_panel, print_memory_panel, print_skills_panel,
    print_sessions_panel, print_search_results, print_cmd_result,
    print_ai_response, print_directive_notice,
    build_prompt_session, get_prompt_text, spinner_context,
    THEME, THEMES, load_theme, set_theme
)
