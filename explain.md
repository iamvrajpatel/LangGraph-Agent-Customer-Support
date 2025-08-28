
## What the project is

A customer-support “Langie” agent that runs an 11-stage workflow. The agent orchestrates calls to two **FastMCP** servers:

* **COMMON** (internal abilities such as parsing, normalization, scoring, response drafting)
* **ATLAS** (external integrations such as entity extraction, KB search, ticketing, notifications)

The simplified runnable agent (`LangGraphAgent`) demonstrates the full workflow without pulling in LangGraph itself, while still doing real (or gracefully mocked) MCP calls.  

---

## Architecture (at a glance)

```
main.py  →  LangGraphAgent
                    │
                    ▼
             MCPClientManager ──► FastMCPClient ──HTTP──► FastMCP Servers
                    ▲                                   (COMMON / ATLAS)
                    │                                             │
               state_models                                @tool functions
```

* **Agent** (`simple_agent.py`) loads `config.yaml`, runs 11 stages in order, logs at each step, and stores everything in a typed state object.
* **Client layer** (`mcp_client.py`): `MCPClientManager` routes a call to the right server; `FastMCPClient` performs HTTP JSON-RPC requests to `…/mcp`, and **falls back** to mock results if servers aren’t up.
* **Servers** (`working_mcp_servers.py`): two FastMCP servers expose discrete `@tool()` abilities (parse, normalize, enrich, evaluate, decide, update ticket, close ticket, KB search, etc.).
* **Demo runners**: `main.py` shows the workflow; `test_with_servers.py` can boot servers then run the demo. 
* **State** (`state_models.py`): a `TypedDict` holding all evolving fields across stages—inputs, derived data, decisions, side-effects, logs, final payload.

**One-line flow:**
Agent → MCPClientManager → FastMCPClient → HTTP → FastMCP Server → Tool → back to Agent (state updates).

---

## Stage modeling (the 11-stage workflow)

The simplified agent executes a fixed list of stages, each mutating state and logging. Server/ability mapping shown per step. 

1. **INTAKE**
   Accept the payload, start the log, record `current_stage`/`completed_stages`. (internal only)

2. **UNDERSTAND**

   * COMMON → `parse_request_text` → `parsed_request` (intent, urgency, etc.)
   * ATLAS → `extract_entities` → `extracted_entities` (account\_id, product…)


3. **PREPARE**

   * COMMON → `normalize_fields` → `normalized_data` (priority, ticket id normalization)
   * ATLAS → `enrich_records` → `enriched_data` (tier, SLA deadline…)
   * COMMON → `add_flags_calculations` → `flags_calculations` (sla\_risk, priority\_score)


4. **ASK**

   * ATLAS → `clarify_question` → set `clarification_question`; mark `clarification_needed=True`. 

5. **WAIT**

   * ATLAS → `extract_answer` → `customer_response`, then internally “store\_answer”; clear `clarification_needed`. 

6. **RETRIEVE**

   * ATLAS → `knowledge_base_search` → `kb_results`; internal “store\_data”. 

7. **DECIDE** (non-deterministic)

   * COMMON → `solution_evaluation` → set `solution_score`.
   * ATLAS → `escalation_decision(solution_score)` → set `escalation_required`, `decision_rationale`.
     *Threshold:* escalate if score < **90** (demo shows 85).  
   * Internal “update\_payload”.

8. **UPDATE**

   * ATLAS → `update_ticket` → `ticket_updated=True`.
   * If **not** escalated: ATLAS → `close_ticket` → `ticket_closed=True`. 

9. **CREATE**

   * COMMON → `response_generation(customer_name)` → `generated_response`. 

10. **DO**

* ATLAS → `execute_api_calls` → record `api_calls_executed`.
* ATLAS → `trigger_notifications` → record `notifications_sent`. 

11. **COMPLETE**
    Compute and store `final_payload` (status = `closed` if ticket was closed else `escalated`, include score, response, completed stages).

---

## State persistence

All state is a single `CustomerSupportState` **TypedDict**, passed and mutated through every stage, guaranteeing persistence without globals. Key groups: inputs, stage tracking, processed data, human interaction, retrieval, decision, updates/actions, final output, logs. The agent appends to `execution_log` and `completed_stages` at each step. 

**Core structures**

* `CustomerSupportState` (TypedDict): authoritative source of truth for the run.
* `InputPayload` (Pydantic): validated inbound payload (`customer_name`, `email`, `query`, `priority`, `ticket_id`).

**Persistence mechanics in code**

* Stage functions mutate the same `state` dict and return it; the driver loop iterates `self.stages` to execute all 11 functions in sequence.
* MCP call results are written into specific state keys (e.g., `parsed_request`, `enriched_data`, `solution_score`), and the final stage synthesizes `final_payload`.

---

## Example execution flow (concrete)

**Input (from demo)**
Customer “John Smith” with a billing issue, `priority="high"`, `ticket_id="12345"`.

**Key results you’ll see**

* `parse_request_text` → `{intent:"billing_inquiry", urgency:"medium"}`.
* `extract_entities` → `{account_id:"ACC123456", product:"Premium Plan"}`.
* `add_flags_calculations` → `{sla_risk:"low", priority_score:65}`.
* `solution_evaluation` → `{score:85, confidence:"high"}` → below threshold → escalate.
* Final payload includes: `status: "escalated"`, `solution_score: 85`, and the generated customer response. 

**How it runs (end-to-end)**

1. `main.py` prints the input and instantiates `LangGraphAgent`, which loads `config.yaml`. 
2. The agent initializes a fresh `CustomerSupportState` and iterates across the 11 stages, calling MCP abilities through `MCPClientManager`.
3. `MCPClientManager` synchronously drives the async `FastMCPClient` (event loop management baked in) to hit `http://localhost:8001/8002/mcp` (or mock on failure).
4. With the demo data, `solution_score=85` → `escalation_required=True` at **DECIDE**, so the ticket is **not** auto-closed in **UPDATE**.
5. **CREATE** drafts a response, **DO** runs API calls/notifications, and **COMPLETE** emits the `final_payload` plus a full execution log and the list of completed stages.

---

## Working details of the MCP integration

* **HTTP JSON-RPC calls**: `FastMCPClient.call_tool(name, **kwargs)` POSTs:

  ```json
  { "method": "tools/call", "params": {"name": "<tool>", "arguments": { ... }}}
  ```

  Returns `.result` or `{error:…}`. On exception, returns **mock** data for that tool so the pipeline keeps going.
* **Server abilities**: Each `@tool()` is a small, focused function returning structured JSON (e.g., `escalation_decision(solution_score)`), hosted by `FastMCP("COMMON")` and `FastMCP("ATLAS")`.
* **Routing**: The agent calls `self._execute_ability(server, ability, state)` with the right server (“COMMON” vs “ATLAS”) pre-mapped per stage.

---

## Quick Reference:

* **Stages**: INTAKE → UNDERSTAND → PREPARE → ASK → WAIT → RETRIEVE → **DECIDE** → UPDATE → CREATE → DO → COMPLETE.
* **State**: Single evolving `CustomerSupportState` dict typed by `TypedDict`.
* **Decision**: Escalate if `solution_score < 90` (demo: 85 → escalated). 
* **Run it**: `python working_working_mcp_servers.py` then `python main.py` or `python test_with_servers.py`. 
