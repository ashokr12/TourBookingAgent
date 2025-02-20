import streamlit as st
from Chat import TravelAssistant, HumanMessage, AIMessage
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Travel Assistant Chat",
    page_icon="✈️",
    layout="centered"
)

# Updated Custom CSS with borders
st.markdown("""
<style>
.title {
    font-size: 2.5rem !important;
    text-align: center;
    padding: 0.5rem 0;
    color: #2c3e50;
    margin-bottom: 1rem;
}
.user-message {
    background-color: #e6f3ff;
    padding: 15px;
    border-radius: 15px;
    margin: 5px 0;
    color: #000000;
    max-width: 80%;
    margin-left: auto;
    border: 1px solid #cce4ff;  /* Light blue border for user messages */
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);  /* Subtle shadow */
}
.assistant-message {
    background-color: #f0f0f0;
    padding: 15px;
    border-radius: 15px;
    margin: 5px 0;
    color: #000000;
    max-width: 80%;
    margin-right: auto;
    border: 1px solid #e0e0e0;  /* Light gray border for assistant messages */
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);  /* Subtle shadow */
}
.chat-container {
    padding: 1rem;
    border-radius: 10px;
    margin-bottom: 1rem;
    height: 500px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;  /* Added border to chat container */
    background-color: white;    /* Explicit white background */
}
.stTextInput>div>div>input {
    border-radius: 20px;
    padding: 10px 15px;
}
.main > div {
    padding-top: 1rem;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 0rem;
    max-width: 800px;
}
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_input" not in st.session_state:
        st.session_state.last_input = None

def display_message(message, is_user=False):
    """Display a single message with appropriate styling"""
    class_name = "user-message" if is_user else "assistant-message"
    
    if isinstance(message, (HumanMessage, AIMessage)):
        content = message.content
    else:
        content = message
        
    st.markdown(f'<div class="{class_name}">{content}</div>', unsafe_allow_html=True)

def display_chat_history():
    """Display all messages in the chat history"""
    for message in st.session_state.chat_history:
        is_user = isinstance(message, HumanMessage)
        display_message(message, is_user)

def process_user_input(user_input: str):
    """Process user input and get AI response"""
    # Check if this input has already been processed
    if user_input != st.session_state.last_input:
        st.session_state.last_input = user_input
        
        # Add user message to messages and chat history
        human_message = HumanMessage(user_input)
        st.session_state.messages.append(human_message)
        st.session_state.chat_history.append(human_message)
        
        try:
            # Get AI response
            config = {"configurable": {"thread_id": "user"}}
            output = TravelAssistant.invoke(
                {"messages": st.session_state.messages}, 
                config
            )
            
            # Update messages and chat history
            st.session_state.messages = output['messages']
            st.session_state.chat_history.append(output['messages'][-1])
            
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            st.error(error_message)

def main():
    # Title with custom styling
    st.markdown('<h1 class="title">✈️ Travel Assistant</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    initialize_session_state()
    
    # Chat container
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        display_chat_history()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Input field with Enter submission
    user_input = st.chat_input(
        placeholder= "Type your message here...",
        key="user_input"
    )
    
    # Process user input when Enter is pressed
    if user_input:
        process_user_input(user_input)
        # Clear the input after processing
        st.rerun()

if __name__ == "__main__":
    main() 