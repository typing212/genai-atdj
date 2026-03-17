# Why LangGraph Over LangChain and Other Agentic Frameworks

## Answer Summary
LangGraph extends LangChain by replacing linear chains with a directed stateful graph, enabling cycles, conditional routing, and shared typed state across all nodes. AT-DJ requires a long-running session loop (3 hours) with validation retries, mid-session user feedback injection, and adaptive replanning — none of which are expressible cleanly in LangChain's AgentExecutor or other high-level frameworks. LangGraph's StateGraph maps directly onto AT-DJ's control flow, making the system's behavior explicit, inspectable, and resumable.

## Key Takeaways
- LangChain = linear pipelines; LangGraph = cyclic directed graph with typed shared state
- LangGraph's key additions: `StateGraph`, conditional edges, `interrupt()` for human-in-the-loop, and built-in `MemorySaver` checkpointing
- AT-DJ's planning loop (plan → validate → retry → publish → loop) is a natural graph cycle — impossible to express cleanly without LangGraph
- Every node in AT-DJ reads and writes the same `AgentState` (session, queue, energy arc, feedback buffer, retry count)
- Alternatives fail for different reasons: OpenAI Assistants is a black box, AutoGen uses free-form messaging, CrewAI is too high-level, plain Python has no checkpointing or interrupt support
- LangGraph's `interrupt()` + `pending_feedback` in state is how AT-DJ handles real-time DJ feedback (energy_up, skip) without restarting the session

## Relevance to AT-DJ Paper
The paper should justify the LangGraph choice by citing the mismatch between AT-DJ's cyclic, stateful control flow and the linear pipeline model of LangChain — framing LangGraph as the enabling technology for long-running agentic sessions with human-in-the-loop feedback. This can be positioned in the System Architecture section as a deliberate design decision over simpler alternatives.
