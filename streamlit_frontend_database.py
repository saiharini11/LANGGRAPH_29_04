import streamlit as st
from langgraph_backend_data import chatbot,retrieve_all_threads, GLOBAL_CONN
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import uuid
from langchain_openai import ChatOpenAI
import sqlite3

# ---------------------------- Utility functions -------------------------------
def generate_thread_id():
# To generate a dynamic random thread id
    thread_id = uuid.uuid4()
    return str(thread_id)

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    st.session_state['thread_title'] = "New Chat"
    
    st.session_state['message_history'] = []

def add_thread(thread_id,thread_title):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append((thread_id,thread_title))
        
def load_conversation(thread_id):
    # Returns messages of a particular thread_id
    CONFIG = {'configurable': {'thread_id' : thread_id}}
    state = chatbot.get_state(config=CONFIG)
    if not state.values or 'messages' not in state.values:
        return []
    return state.values['messages']

def generate_title(user_message):
    model = ChatOpenAI()
    prompt = f"Give a very short 3 to 5 word title for this conversation : \n {user_message}"

    result = model.invoke(prompt)
    title = result.content.strip()
    return title

# def delete_from_checkpointer(thread_id):
#     """
#     Deletes all LangGraph checkpoints (actual conversation history)
#     for a given thread_id from the SqliteSaver backend.
#     """
#     # These are internal tables used by SqliteSaver
#     GLOBAL_CONN.execute("DELETE FROM checkpoints where thread_id = ?",(thread_id,))
#     GLOBAL_CONN.execute("DELETE FROM writes where thread_id = ?",(thread_id,))
#     GLOBAL_CONN.commit()

def clear_conversation(thread_id):
    """
    Safely clears conversation without corrupting DB.
    """
    CONFIG = {"configurable": {"thread_id": thread_id}}
    chatbot.update_state(
        config = CONFIG,
        values = {'messages':[]}
    )


def delete_thread(thread_id):
    # Remove from session
    st.session_state['chat_threads'] = [
        (tid,title) for tid,title in st.session_state['chat_threads'] if tid!=thread_id
    ]
    # Remove from DB
    conn=sqlite3.connect('chatbot.db')
    conn.execute("DELETE FROM thread_meta where thread_id = ?",(thread_id,))
    conn.commit()
    conn.close()
    

    # Remove from LangGraph checkpoint storage (actual messages)
    clear_conversation(thread_id)

    # Reset if active
    if(st.session_state['thread_id']==thread_id):
        reset_chat()
    
    st.rerun()




# ------------------ Session setup -----------------------------------
if 'message_history' not in st.session_state:
    st.session_state['message_history'] =[]

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'thread_title' not in st.session_state:
    st.session_state['thread_title'] = "New Chat"

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()

if 'active_menu_thread' not in st.session_state:
    st.session_state['active_menu_thread'] = None



# ---------------------- Sidebar UI ------------------------------
# ---------------------- Sidebar UI controller utility functions   --------------------
# ---------------------- Load chat ---------------------------------

def format_messages(messages):
    """
    Convert Langchain message objects into UI friendly format.
    Output format:
    [{"role: 'user', content: 'Hi'}, --- ]
    """
    formatted = []
    for msg in messages:
        if isinstance(msg,HumanMessage):
            role='user'
        else:
            role='assistant'
        formatted.append({'role':role, 'content':msg.content })
    return formatted
    
def render_load_button(col,thread_id,title):
    """ 
    Handles loading a conversation when use clicks on chat title.
    Updates session state with selected thread and messages.
    """
    if col.button(title,key=f"load_{thread_id}"):
        st.session_state['thread_id'] = thread_id
        st.session_state['thread_title'] = title
        messages = load_conversation(thread_id)
        st.session_state['message_history'] = format_messages(messages)


# -------------------- Three dot menu ---------------------------------------
def toggle_active_menu(thread_id):
    """
    Opens or closes dropdown menu for a thread.
    Only one menu is active at a time.
    """
    if st.session_state['active_menu_thread'] == thread_id:
        st.session_state['active_menu_thread'] = None
    else:
        st.session_state['active_menu_thread'] = thread_id

def render_menu_button(col,thread_id):
    """
    Handles ... function.
    Toggles which thread's dropdown menu is currently open.
    """
    if col.button("...",key=f"menu_{thread_id}"):
        toggle_active_menu(thread_id)

# ---------------------- Delete button ---------------------------------------
def render_delete_button(col,thread_id):
    """
    Deletes the thread when clicked on it.
    """
    if col.button("🗑 Delete",key=f"delete_{thread_id}"):
        delete_thread(thread_id)
                  
# ---------------------- Dropdownm menu --------------------------------------
def render_dropdown_menu(thread_id):
    """
    Displays dropdown options (Like delete) only for the currently active thread.
    """
    if st.session_state['active_menu_thread'] == thread_id:
        sub_col1,sub_col2 = st.sidebar.columns([0.1,0.9])
        render_delete_button(sub_col2,thread_id)

# ---------------------- Sidebar UI controller -------------------------------
# ---------------------- Each thread row -------------------------------------

def render_thread_row(thread_id,title):
    """
    Renders a single row in sidebar:
    - Chat title button (to load conversation)
    - Three-dot menu button
    - Conditional dropdown (Delete)
    """
    col1,col2 = st.sidebar.columns([0.85,0.15])
    render_load_button(col1,thread_id,title)
    render_menu_button(col2,thread_id)
    render_dropdown_menu(thread_id)

# ---------------------- Main sidebar controller ------------------------------
def render_sidebar_threads():
    """
    Main function to render all chat threads in the sidebar.
    Iterates through threads and calls smaller UI components.
    """
    st.sidebar.header('My Conversations')
    st.sidebar.title('LangGraph Chatbot')
    if st.sidebar.button('New Chat'):
        reset_chat()
    st.sidebar.header('My Conversations')
    for thread_id,title in st.session_state['chat_threads'][::-1]:
        render_thread_row(thread_id,title)


render_sidebar_threads()


# ------------------------------------  Main UI -------------------------------------

# Loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

user_input=st.chat_input('Type here')

if user_input:
    st.session_state['message_history'].append({'role':'user','content':user_input})
    new_thread_created=False
    if(st.session_state['thread_title']=="New Chat"):
        title=generate_title(user_input)
        st.session_state['thread_title'] =  title
        #st.session_state['chat_threads'][-1][st.session_state['thread_id']]=title
        add_thread(st.session_state['thread_id'],st.session_state['thread_title'] )
        conn=sqlite3.connect('chatbot.db')
        conn.execute(
            "INSERT OR REPLACE INTO thread_meta (thread_id,title) VALUES (?,?)",
            (str(st.session_state['thread_id']),st.session_state['thread_title'])
        )
        conn.commit()
        conn.close()
        new_thread_created=True
    with st.chat_message('user'):
        st.markdown(user_input)
    
    # CONFIG = {'configurable': {'thread_id' : st.session_state['thread_id']}}
    # Also includes langsmith tracing threadwise
    CONFIG = {'configurable': {'thread_id' : st.session_state['thread_id']},
              "metadata": {
                  'thread_id' : st.session_state['thread_id']
              },
              "run_name": "chat_turn"
              }
    with st.chat_message('assistant'):
        # Streaming
        ai_message = st.write_stream(
            message_chunk.content for message_chunk,metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,stream_mode='messages'
            )
        )
    st.session_state['message_history'].append({'role':'assistant','content':ai_message})
    if new_thread_created:
        st.rerun()

    

