import os
from typing import List, Optional
from dotenv import load_dotenv
from ragflow_sdk import RAGFlow
from ragflow_sdk.ragflow import Chat, Chunk, DataSet
from ragflow_sdk.modules.session import Session, Message
from typing import Generator, Any


load_dotenv()

RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY")
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL")

class ChatService:
    def __init__(self):
        """
        初始化 ChatService，创建 RAGFlow 客户端。
        """
        if not RAGFLOW_API_KEY or not RAGFLOW_BASE_URL:
            raise ValueError("RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL 必须在 .env 文件中设置")
        self.rag_flow = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)

    def create_chat_assistant(self, name: str, dataset_ids: List[str]) -> Chat:
        """
        创建一个聊天助手。

        :param name: 聊天助手的名称。
        :param dataset_ids: 关联的数据集ID列表。
        :return: 代表聊天助手的 Chat 对象。
        """
        assistant = self.rag_flow.create_chat(name=name, dataset_ids=dataset_ids)
        return assistant

    def delete_chat_assistant(self, assistant_ids: List[str]):
        """
        根据ID删除聊天助手。

        :param assistant_ids: 要删除的聊天助手的ID列表。
        """
        self.rag_flow.delete_chats(ids=assistant_ids)

    def list_chat_assistants(self,  page: int = 1, page_size: int = 30,   id: str | None = None, name: str | None = None) -> list[Chat]:
        """
        列出所有聊天助手。

        :return: Chat 对象的列表。
        """
        return self.rag_flow.list_chats(page=page, page_size=page_size, id=id, name=name)

    def create_session(self, assistant_id: str, session_name: str = "New session") -> Session:
        """
        通过其ID与聊天助手创建会话。

        :param assistant_id: 聊天助手的ID。
        :param session_name: 新会话的名称。
        :return: 一个 Session 对象。
        """
        assistants = self.rag_flow.list_chats(id=assistant_id)
        if not assistants:
            raise ValueError(f"未找到ID为 {assistant_id} 的助手")
        assistant = assistants[0]
        session = assistant.create_session(name=session_name)
        return session

    def list_sessions(self, assistant_id: str, page: int = 1, page_size: int = 30) -> list[Session]:
        """
        列出指定聊天助手的所有会话。

        :param assistant_id: 聊天助手的ID。
        :param page: 页码。
        :param page_size: 每页数量。
        :return: Session 对象的列表。
        """
        assistants = self.rag_flow.list_chats(id=assistant_id)
        if not assistants:
            raise ValueError(f"未找到ID为 {assistant_id} 的助手")
        assistant = assistants[0]
        return assistant.list_sessions(page=page, page_size=page_size)

    def delete_session(self, assistant_id: str, session_ids: List[str]):
        """
        通过ID删除聊天助手的会话。

        :param assistant_id: 聊天助手的ID。
        :param session_ids: 要删除的会话ID列表。
        """
        assistants = self.rag_flow.list_chats(id=assistant_id)
        if not assistants:
            raise ValueError(f"未找到ID为 {assistant_id} 的助手")
        assistant = assistants[0]
        assistant.delete_sessions(ids=session_ids)

    def ask_question(self, assistant_id: str, assistant_name: Optional[str], session_id: str, session_name: Optional[str], question: str, stream: bool = True) -> Generator[Message, Any, Message | None]:
        """
        向聊天助手的特定会话提问。

        :param assistant_id: 聊天助手的ID。
        :param assistant_name: 聊天助手的名称 (可选)。
        :param session_id: 会话的ID。
        :param session_name: 会话的名称 (可选)。
        :param question: 要提出的问题。
        :param stream: 是否对响应使用流式传输。(没写非流式, 只能用流式)
        :return: 一个 Message 对象或 Message 对象的迭代器。
        """
        list_chats_args = {"id": assistant_id}
        if assistant_name:
            list_chats_args["name"] = assistant_name
        
        assistants = self.rag_flow.list_chats(**list_chats_args) # type: ignore
        if not assistants:
            raise ValueError(f"未找到ID为 {assistant_id} 的助手")
        assistant = assistants[0]
        
        list_sessions_args = {"id": session_id}
        if session_name:
            list_sessions_args["name"] = session_name
            
        sessions = assistant.list_sessions(**list_sessions_args)  # type: ignore
        if not sessions:
            raise ValueError(f"未找到ID为 {session_id} 的会话 (助手ID: {assistant_id})")
        session = sessions[0]
        
        return session.ask(question=question, stream=stream)
    
# #%%
# from ragflow_sdk import RAGFlow
# from ragflow_sdk.ragflow import Chat
# import os

# RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY")
# RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL")

# rag_object = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)

# datasets = rag_object.list_datasets(name="1")
# dataset_ids = [dataset.id for dataset in datasets]

# prompt = Chat.Prompt(
#     rag_object,
#     {
#         "opener": "你好",
#         "prompt": "你是一个物理老师，请根据知识库内容出一道质点运动题目"
#     }
# )

# # 生成唯一的聊天助手名称，避免名称重复异常
# unique_name = "Miss R"

# assistant = rag_object.list_chats(name=unique_name)[0]
# print(assistant.id)

# session = assistant.list_sessions()[0]

# # %%
# while True:
#     question = input("\n==================== User =====================\n> ")
#     print("\n==================== Miss R =====================\n")
    
#     try:
#         ans = session.ask(question, stream=True)
#         for line in ans:
#             print(line.content, end='', flush=True)
            
#     except Exception as e:
#         print(f"出错: {str(e)}")
# #%%
