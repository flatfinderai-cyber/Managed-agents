# Managed Agents Policy (LLM Instructions)

1. Follow this policy exactly when creating and running managed autonomous agent workflows.
2. Treat these entities as separate required objects:
   1. Agent: model configuration, system instructions, and tool configuration.
   2. Environment: container runtime configuration (packages, networking, execution context).
   3. Session: one running task instance bound to one agent and one environment.
   4. Events: all input, output, and status updates exchanged during the session.
3. Never hardcode secrets (API keys, tokens, passwords) in prompts, code, docs, logs, or requests.
4. Read secrets from environment variables only.
5. Before any API request, verify required credentials exist and are non-empty. If missing, stop and return a clear credential error.
6. For direct Anthropic HTTP requests, include all required headers:
   1. `x-api-key: $ANTHROPIC_API_KEY`
   2. `anthropic-version: 2023-06-01`
   3. `anthropic-beta: managed-agents-2026-04-01`
   4. `content-type: application/json`
7. If any required Anthropic header is missing, stop and return a configuration error.
8. If using an official SDK, use the managed-agents beta APIs.
9. Create the agent first.
10. When creating the agent, set all of the following explicitly:
    1. Name
    2. Model
    3. System prompt
    4. Toolset (`agent_toolset_20260401`) unless stricter tool policy is required
11. Persist and return both `agent.id` and `agent.version` after agent creation.
12. Create the environment second.
13. When creating the environment, set all of the following explicitly:
    1. Name
    2. Config type: `cloud`
    3. Networking policy (for quickstart: `unrestricted`)
14. Persist and return `environment.id` after environment creation.
15. Create the session third.
16. When creating the session, set all of the following:
    1. `agent` = saved `agent.id`
    2. `environment_id` = saved `environment.id`
    3. A human-readable `title`
17. Persist and return `session.id` after session creation.
18. Open a session event stream and keep it active until completion.
19. Send user input as a `user.message` event with text content blocks.
20. Handle streaming events with deterministic rules:
    1. On `agent.message`: output text content in order.
    2. On `agent.tool_use`: log tool name and continue.
    3. On `session.status_idle`: mark complete and stop streaming.
    4. On unknown event types: ignore safely unless logging is required by policy.
21. Assume tool execution occurs inside the configured container environment, not on the client host.
22. Preserve event order and do not drop events.
23. If stream fails before `session.status_idle`, retry safely or return a recoverable runtime error with context.
24. Validate completion with observable outcomes (expected files, command success, or explicit agent confirmation).
25. Do not claim completion until `session.status_idle` is observed or a terminal error is returned.
26. Return a final structured result containing:
    1. Agent ID and version
    2. Environment ID
    3. Session ID
    4. Output summary
    5. Completion state (`idle reached` or `not reached`)
27. After successful execution, recommend next steps to improve agent definition, environment constraints, tool permissions, and event handling.
