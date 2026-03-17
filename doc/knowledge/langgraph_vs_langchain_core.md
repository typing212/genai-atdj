# LangGraph vs LangChain Core — Layer Distinction

## Answer Summary
`langchain-core` is a low-level shared abstraction library that defines the building blocks of the LangChain ecosystem — message types, tool interfaces, LLM base classes, and composition primitives — with no opinion on control flow. LangGraph is an orchestration framework built on top of `langchain-core` that adds a stateful graph engine with cycles, conditional routing, checkpointing, and human-in-the-loop support. The two are independently installable and separable: you could replace LangGraph with a different orchestrator and still use `langchain-core` types throughout.

## Key Takeaways
- `langchain-core` = the **protocol/type layer**: defines `BaseMessage`, `BaseTool`, `@tool`, `BaseLanguageModel`, `add_messages`, and pipe (`|`) composition
- LangGraph = the **control flow layer**: defines `StateGraph`, nodes, edges, cycles, `interrupt()`, and `MemorySaver` checkpointing
- `langchain-anthropic` = the **adapter layer**: connects Claude specifically to the `langchain-core` LLM interface
- They are separately installable — swapping LangGraph for a different orchestrator does not require changing tool or message definitions
- Analogy: `langchain-core` is the electrical standard (plug/voltage); LangGraph is the circuit board (routing); `langchain-anthropic` is the power adapter (Claude-specific connector)
- In AT-DJ, `langchain-core` provides `AgentState`'s `add_messages` reducer and all `@tool` definitions; LangGraph provides the `StateGraph` that routes between `tanda_planner`, `cortina_selector`, `feedback_handler`, etc.

## Relevance to AT-DJ Paper
The System Architecture section should distinguish these two layers to show architectural clarity — `langchain-core` as the interoperability foundation and LangGraph as the deliberate orchestration choice, emphasizing that the LLM backbone (Claude) is swappable without changing the graph structure.