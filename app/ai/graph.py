from __future__ import annotations

from typing import Literal, TypedDict, Annotated
import operator

from langchain_core.messages import BaseMessage, HumanMessage
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


def create_agent(llm: ChatGroq, tools: list, system_message: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    return prompt | llm.bind_tools(tools)


class AiGraph:
    def __init__(self):
        self.tools = [get_question_details, get_user_weak_topics]
        self.agent_runnable = create_agent(llm, self.tools, "You are a helpful AI assistant.")
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self.agent_runnable)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.set_entry_point("agent")

        def should_continue(state: AgentState) -> Literal["tools", END]:
            messages = state["messages"]
            last_message = messages[-1]
            if not last_message.tool_calls:
                return END
            return "tools"

        workflow.add_conditional_edge("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def invoke(self, input_message: str, config: dict):
        return await self.graph.ainvoke({"messages": [HumanMessage(content=input_message)]}, config)
