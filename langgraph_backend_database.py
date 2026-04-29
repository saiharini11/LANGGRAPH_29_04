from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
#from langchain_huggingface import ChatHuggingFace,HuggingFaceEndpoint
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

load_dotenv()

model = ChatOpenAI(model = "gpt-4o-mini")


class ChatState(TypedDict):
    # Reducer function add - To append
    messages: Annotated[list[BaseMessage],add_messages]

def chat_node(state:ChatState):
    # Take user query from state
    messages = state['messages']
    # Send to llm
    response = model.invoke(messages)
    # response store in state
    return {'messages':[response]}

# Creates database in same folder as code
GLOBAL_CONN = sqlite3.connect(database='chatbot.db', check_same_thread=False, isolation_level=None)

# SQL configuration
GLOBAL_CONN.execute("PRAGMA journal_mode=DELETE;")

# Create table to map thread_id and thread_title
GLOBAL_CONN.execute("""
CREATE TABLE IF NOT EXISTS thread_meta (
             thread_id TEXT PRIMARY KEY,
             title TEXT
)
""")
GLOBAL_CONN.commit()

# Checkpointer
checkpointer = SqliteSaver(conn=GLOBAL_CONN)
# Define graph
graph = StateGraph(ChatState)

# Add nodes
graph.add_node('chat_node',chat_node)

# Add edges
graph.add_edge(START,'chat_node')
graph.add_edge('chat_node',END)

chatbot = graph.compile(checkpointer=checkpointer)

# # Gives all checkpoints - generator object
# checkpointer.list(None)
# def retrieve_all_threads():
# # Get unique threads in database
#     all_threads=set()
#     for checkpoint in checkpointer.list(None):
#         all_threads.add(checkpoint.config['configurable']['thread_id'])
#     return list(all_threads)

def retrieve_all_threads():
    rows = GLOBAL_CONN.execute("SELECT thread_id,title FROM thread_meta").fetchall()
    return [(str(thread_id),title) for thread_id,title in rows]

