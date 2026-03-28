from __future__ import annotations

from typing import Literal, TypedDict, Annotated
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq

from app.core.config import settings
from app.ai.tools import get_question_details, get_user_weak_topics # Import actual tools


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


llm = ChatGroq(temperature=0, groq_api_key=settings.groq_api_key, model_name=settings.groq_model)


def create_agent(llm: ChatGroq, tools: list):
    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="messages"),
    ])
    return prompt | llm.bind_tools(tools)


class AiGraph:
    def __init__(self):
        # Remove get_question_details to save DB connections since context is provided in prompt
        self.tools = [get_user_weak_topics]
        self.agent_runnable = create_agent(llm, self.tools)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        async def call_agent(state):
            response = await self.agent_runnable.ainvoke(state)
            return {"messages": [response]}

        workflow.add_node("agent", call_agent)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.set_entry_point("agent")

        def should_continue(state: AgentState) -> Literal["tools", END]:
            messages = state["messages"]
            last_message = messages[-1]
            # Ensure we only check tool_calls on AIMessages that actually have them
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def invoke(self, input_message: str, system_instructions: str, config: dict):
        # Prepend system instructions as a SystemMessage to ensure they are followed
        messages = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=input_message)
        ]
        return await self.graph.ainvoke({"messages": messages}, config)
