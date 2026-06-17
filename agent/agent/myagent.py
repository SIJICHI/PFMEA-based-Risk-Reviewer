# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""製剤工程 PFMEA ナレッジ検索エージェント.

利用者の自然言語の質問を ``pfmea_search`` ツールに渡して関連 PFMEA レコードを
取得し、その結果のみに基づいて回答する単一エージェント (SPEC 5.4 / 6)。
"""

from typing import TYPE_CHECKING, Optional

import litellm
from datarobot_genai.core.agents import InvokeReturn, make_system_prompt
from datarobot_genai.core.agents.base import UsageMetrics
from datarobot_genai.core.chat import agent_chat_completion_wrapper
from datarobot_genai.core.mcp import MCPConfig
from datarobot_genai.langgraph.agent import datarobot_agent_class_from_langgraph
from datarobot_genai.langgraph.llm import get_llm
from datarobot_genai.langgraph.mcp import mcp_tools_context
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from openai.types.chat import CompletionCreateParams

from agent.tools import pfmea_search

if TYPE_CHECKING:
    from ragas import MultiTurnSample

litellm.modify_params = True

_PLACEHOLDER_MODELS = frozenset({"unknown"})


# 利用者の質問を {topic} として受け取り、過去履歴は {chat_history} で参照する。
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "あなたは製剤工場（固形製剤ライン）の PFMEA ナレッジ検索アシスタント"
            "です。過去の会話履歴は {chat_history} から参照できます（空の場合も"
            "あります）。一貫した回答のために必要に応じて活用してください。",
        ),
        (
            "user",
            "{topic}",
        ),
    ]
)


# SPEC 5.4: 検索結果に基づくのみで回答し、レコードIDを根拠として併記させる。
PFMEA_SYSTEM_PROMPT = (
    "あなたは製薬工場の固形製剤製造ライン（秤量〜包装）の技術者を支援する "
    "PFMEA ナレッジ検索アシスタントです。\n"
    "\n"
    "【行動原則】\n"
    "1. 工程の不良現象・リスク・原因・対策に関する質問には、必ず "
    "`pfmea_search` ツールを呼び出し、過去の PFMEA レコードを検索すること。\n"
    "2. 回答はツールの検索結果に含まれる情報のみに基づくこと。検索結果に無い"
    "事実を推測・創作してはならない。\n"
    "3. 参照した各レコードについて、必ず record_id（例: F0601）を根拠として"
    "併記すること。\n"
    "4. 故障モード・影響・主な要因・現在の管理・推奨対策・RPN を、利用者が"
    "理解しやすいよう日本語で簡潔に整理して提示すること。RPN が高いものほど"
    "優先度が高いリスクである点に触れること。\n"
    "5. 検索結果が空（該当なし）の場合は、その旨を伝え、ツールが返した"
    "言い換え例を案内すること。PFMEA と無関係な質問（天気など）には、本"
    "アシスタントは製剤工程の PFMEA 検索専用である旨を丁寧に伝えること。\n"
    "6. 本データは技術検討用の架空サンプルである点に留意すること。"
)


def graph_factory(
    llm: BaseChatModel, tools: list[BaseTool], verbose: bool = False
) -> StateGraph[MessagesState]:
    """PFMEA 検索ツールを備えた単一エージェントのグラフを構築する。"""
    all_tools = [pfmea_search, *tools]
    pfmea_assistant = create_agent(
        llm,
        tools=all_tools,
        system_prompt=make_system_prompt(PFMEA_SYSTEM_PROMPT),
        name="pfmea_assistant",
        debug=verbose,
    )

    workflow = StateGraph(MessagesState)
    workflow.add_node("pfmea_assistant", pfmea_assistant)
    workflow.add_edge(START, "pfmea_assistant")
    workflow.add_edge("pfmea_assistant", END)
    return workflow


MyAgent = datarobot_agent_class_from_langgraph(graph_factory, prompt_template)


async def custompy_adaptor(
    completion_create_params: CompletionCreateParams,
) -> InvokeReturn | tuple[str, Optional["MultiTurnSample"], UsageMetrics]:
    forwarded_headers = completion_create_params.get("forwarded_headers", {})
    authorization_context = completion_create_params.get("authorization_context", {})
    mcp_config = MCPConfig(
        forwarded_headers=forwarded_headers,
        authorization_context=authorization_context,
    )
    mcp_tools_factory = lambda: mcp_tools_context(mcp_config)  # noqa: E731
    model_name = completion_create_params.get("model")
    agent = MyAgent(
        llm=get_llm(
            model_name=model_name if model_name not in _PLACEHOLDER_MODELS else None
        ),
        verbose=completion_create_params.get("verbose", True),  # type: ignore[arg-type]
        timeout=completion_create_params.get("timeout", 90),  # type: ignore[arg-type]
        forwarded_headers=forwarded_headers,  # type: ignore[arg-type]
    )
    return await agent_chat_completion_wrapper(
        agent, completion_create_params, mcp_tools_factory
    )
