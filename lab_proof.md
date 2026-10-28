# Lab Proof: Agents that speak MCP fluently

One query goes through one LangChain agent, which calls tools on MCP servers. A reviewer can trace each claim in the final answer to a raw tool output.

**How to review:** open [`mcp_langchain.ipynb`](mcp_langchain.ipynb). It was run from top to bottom and all outputs are saved. [`evidence.json`](evidence.json) holds the same trace as data.

> Note: local absolute paths in the saved notebook outputs and `evidence.json` were redacted to `<LAB>` (this repo) and `<GIT_SOURCE_REPO>` (the git source clone) for privacy; nothing else was edited.

**How to run it yourself**
```bash
git clone https://github.com/langchain-ai/langchain-mcp-adapters   # git source; HEAD 52a4535 at time of the run
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                                    # Node.js/npx is also needed for the filesystem server
# .env: OPENAI_API_KEY=...   GIT_SOURCE_REPO=/path/to/langchain-mcp-adapters
jupyter nbconvert --to notebook --execute mcp_langchain.ipynb      # or open it and run all cells
```

## 1. Code / workflow

| Step | What happens | Where |
|---|---|---|
| INPUT | A question about the langchain-mcp-adapters git history and its README | notebook, "Run one query" |
| DECIDE | Tool path: the agent picks tools from two MCP servers | notebook, Step 4/6 |
| BUILD | `MultiServerMCPClient` connects 3 MCP servers → `get_tools()` → keep 12 read-only tools → `create_agent` (gpt-4o-mini, temperature 0) | notebook, Steps 1–6 |
| VERIFY | Trace view of every tool call and output, plus an automatic grounding check | notebook, VERIFY cells |
| EXPLAIN | Failure probe with a question the sources cannot answer | notebook, EXPLAIN cell |

**MCP servers**

| Server | Source | Provides |
|---|---|---|
| `filesystem` | official `@modelcontextprotocol/server-filesystem`, restricted to [`docs/`](docs/) | tools to read and search the docs |
| `git` | official `mcp-server-git`, pointed at a clone of `langchain-ai/langchain-mcp-adapters` (`GIT_SOURCE_REPO`) | tools for log / show / diff |
| `docs` | [`docs_resource_server.py`](docs_resource_server.py), custom FastMCP server | resources: `docs://*.md` |

**Design choices**
- **Two sources a reviewer can check.** The docs folder and the git history are both fixed sources that the reviewer can open, unlike a live web page that can change.
- **A third server for resources.** The official filesystem and git servers return `Method not found` for resources, so the small `docs` server covers Step 5. Only a *catalog* of resources (URI and title) goes into the system prompt, not the full text. The agent still has to call a tool to quote anything, so every quote shows up in the trace.
- **Read-only tools.** The agent gets 12 of the 26 tools. `write_file`, `edit_file`, `git_commit`, `git_reset` and similar tools are filtered out.
- **Filesystem limited to `docs/`.** Pointing it at the repo root would let the agent read `.env`.
- **Size guardrail, using the adapter's `tool_interceptors`.** `git_log` is shortened to one line per commit and capped at 20 commits. Any other output over 8,000 characters is cut, and a visible `[TRUNCATED…]` marker is added. Each agent run is capped at 25 steps (`recursion_limit=25`). Section 5 explains why these were needed.
- **Practical example (Step 8).** The setup is a small document analysis agent: a filesystem MCP server pointed at a documents folder, an agent prompt specialized for answering from those documents, and queries that list, read and search them.
- **Method name in this version.** In langchain-mcp-adapters 0.3.2 the method is `client.get_tools()`. The `get_langchain_tools()` named in the lab text does not exist.

## 2. Query

> Which commit capped the mcp dependency below 2.0.0, and what exactly changed in pyproject.toml? Also, according to the README, how do I connect to multiple MCP servers at once?

To answer this, the agent needs both tool servers: git for the commit and the diff, and the filesystem for the README.

## 3. Tool evidence

The agent made three tool calls:

```
>>> git_log({"repo_path": "<GIT_SOURCE_REPO>", "max_count": 20})                       → 3,259 chars
>>> read_text_file({"path": "<LAB>/docs/langchain_mcp_adapters_README.md"})            → 8,046 chars (truncated by guardrail)
>>> git_show({"repo_path": "<GIT_SOURCE_REPO>", "revision": "d4a1caa9fb76f8f5206e274c60abe8bd5a3a2599"}) → 2,077 chars
```

**`git_log`** (shortened by the guardrail). This is where the commit was found:
```
d4a1caa9fb76f8f5206e274c60abe8bd5a3a2599 | 2026-08-06 13:04:50+08:00 | 石岳峰 | fix(deps): cap mcp below 2.0.0 to prevent import failures (#590)
```

**`git_show d4a1caa`**. This is the evidence for the change and the reason behind it:
```
    `mcp` 2.0.0 removed `RequestContext` from `mcp.shared.context`, but this
    package still imports it in `callbacks.py`. ...
--- pyproject.toml
+++ pyproject.toml
@@ -14,7 +14,7 @@ readme = "README.md"
 dependencies = [
     "langchain-core>=1.3.3,<2.0.0",
-    "mcp>=1.24.0",
+    "mcp>=1.24.0,<2.0.0",
     "typing-extensions>=4.14.0",
 ]
```

**`read_text_file` README**. The `MultiServerMCPClient` example starts at character 3,678 of the README, so it falls inside the first 8,000 characters the agent actually received:
```python
client = MultiServerMCPClient(
    {
        "math": {"command": "python", "args": ["/path/to/math_server.py"], "transport": "stdio"},
        "weather": {"url": "http://localhost:8000/mcp", "transport": "http"},
    }
)
tools = await client.get_tools()
```

## 4. Final output

**Agent answer (condensed and reworded; the full, exact text is in the notebook and in `evidence.json` under `final_answer`):**

> The commit that capped the MCP dependency below 2.0.0 is **d4a1caa9fb76f8f5206e274c60abe8bd5a3a2599**. In `pyproject.toml` the `mcp` dependency changed from `"mcp>=1.24.0"` to `"mcp>=1.24.0,<2.0.0"`. This change was made to prevent import failures when new installations resolved to MCP SDK 2.x, which removed components the package uses *(git_show d4a1caa9)*.
>
> According to the README, use `MultiServerMCPClient` with one entry per server (example: a `math` stdio server and a `weather` HTTP server), then `await client.get_tools()` and pass the tools to `create_agent` *(file: langchain_mcp_adapters_README.md)*.

**Automatic grounding check: 17/17 claims supported.** Every commit hash, every inline code span and every line of the code blocks in the answer appears word for word in a tool output:

```
✓ d4a1caa9fb76f8f5206e274c60abe8bd5a3a2599     ✓ "mcp>=1.24.0"        ✓ "mcp>=1.24.0,<2.0.0"
✓ client = MultiServerMCPClient(               ✓ "transport": "stdio", ✓ tools = await client.get_tools()
... (17/17 checkable claims found verbatim in tool output)
```

The reviewer can check this by hand: in the langchain-mcp-adapters clone, run `git show d4a1caa -- pyproject.toml` and compare it with the answer.

## 5. Failure / limitation

These failures were observed while building the lab. Rows 1–3 come from earlier development runs, before the guardrail was in place; rows 4–5 can be seen in the saved notebook:

| # | What happened | Evidence | Fix / status |
|---|---|---|---|
| 1 | **The context window overflowed.** The agent called `git_log(max_count=50)`, the output was 516k characters (long dependabot commit messages), and the request failed with a 128k-token context error. | first notebook run | Fixed: `git_log` shortened to one line per commit, capped at 20 |
| 2 | **Truncation hid the evidence.** Cutting outputs at 8k removed commit `d4a1caa`, and the agent looped, calling tools again and again to find it. | second run, `GraphRecursionError` | Fixed: shorten instead of cut, plus a 25-step limit |
| 3 | **Invented argument.** In one run the agent called `git_show(revision="<commit_sha>")`, a placeholder, before it had a real hash. | diagnostic run | Open: the git server returned an error and the agent recovered |
| 4 | **Unanswerable question gave no answer.** Asked *"On what date was version 0.4.0 released, and who approved it?"* (no such release exists), the agent never said "Not found in sources" and ran into the step limit. | EXPLAIN cell: `NO ANSWER: GraphRecursionError after 25 steps` | Open |
| 5 | **Only part of the README is visible.** The guardrail cuts the README at 8,000 of 11,924 characters, so the agent cannot see anything after that point. | `read_text_file` output ends with `[TRUNCATED…]` | Open (known trade-off) |

**Where could the system produce a plausible but unsupported answer?**

The most likely place is past the truncation point. The guardrail cuts the README at 8,000 of its 11,924 characters, so the agent never sees the last third. An earlier version of the same guardrail cut git_log and removed the very commit we needed, and the agent kept searching for it. My lesson is; cutting output can delete your evidence. Then We used the adapter's tool_interceptors, a hook that runs before and after every tool call, to shrink git_log to one line per commit. Every commit stayed visible at a fraction of the size. 

The second risk is that the "say Not found in sources" rule is only a prompt instruction. The prompt said "say Not found in sources", but the agent ignored that and looped until the step limit stopped it. A rule in the prompt is a request, not a guarantee. If you need the agent to say "I don't know", you have to enforce it in code. My lesson is: Make the agent say "I don't know" in code.

One improvement I would make next: require the agent to back each claim with a direct quote from a tool output, and check every quote word for word against the saved tool outputs. If a quote isn't found, or the agent hits the step limit, return "Not found in sources" instead of a generated answer. Abstaining would then happen in code instead of depending on the prompt.

*AI use: Claude Code was used for setup, debugging and drafting sections 1–4 from the run outputs; section 5's analysis is my own.*
