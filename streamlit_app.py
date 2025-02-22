import streamlit as st
from Chat import TravelAssistant, HumanMessage, AIMessage, State
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Welcome to BlingDestinations",
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
    height: 10px;
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
.carousel-image {
    width: 100%;
    height: 300px;  /* Increased from 200px to 300px */
    object-fit: cover;
    border-radius: 10px;
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
    if "email" not in st.session_state:
        st.session_state.email = ""
    if "mobile" not in st.session_state:
        st.session_state.mobile = ""
    if "name" not in st.session_state:
        st.session_state.name = ""

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
            # Create initial state with user details
            initial_state = {
                "messages": st.session_state.messages,
                "user_email": st.session_state.email,
                "user_mobile": st.session_state.mobile,
                "user_name": st.session_state.name  # Add name to state
            }
            
            # Add required configurable keys
            config = {
                "configurable": {
                    "thread_id": st.session_state.email,
                    "checkpoint_ns": "travel_assistant",
                    "checkpoint_id": str(int(time.time()))
                }
            }
            
            # Invoke TravelAssistant with state and config
            output = TravelAssistant.invoke(initial_state, config)
            
            # Update messages and chat history
            st.session_state.messages = output['messages']
            st.session_state.chat_history.append(output['messages'][-1])
            
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            st.error(error_message)

def create_image_carousel():
    """Create an image carousel with destination images showing 3 images at once"""
    # List of image paths - update these with your actual image paths
    images = [
        "assets/Australia.jpg",
        "assets/Bali.jpg",
        "assets/Dubai.jpg",
        "assets/Europe1.jpg",
        "assets/Europe2.jpg",
        "assets/Mauritius.jpg",
        "assets/SouthAfrica.jpg",
        "assets/Thailand.jpg",
    ]
    
    # Initialize carousel index in session state
    if "carousel_index" not in st.session_state:
        st.session_state.carousel_index = 0
    
    # Create columns for the carousel with adjusted ratios
    col1, col2, col3, col4, col5 = st.columns([0.5, 3.5, 3.5, 3.5, 0.5])  # Modified column ratios
    
    with col1:
        if st.button("←"):
            st.session_state.carousel_index = (st.session_state.carousel_index - 3) % len(images)
            
    # Display 3 images in the middle columns
    try:
        with col2:
            idx = st.session_state.carousel_index % len(images)
            st.image(images[idx], use_container_width=True)
        
        with col3:
            idx = (st.session_state.carousel_index + 1) % len(images)
            st.image(images[idx], use_container_width=True)
            
        with col4:
            idx = (st.session_state.carousel_index + 2) % len(images)
            st.image(images[idx], use_container_width=True)
            
    except FileNotFoundError:
        st.error("Image files not found. Please ensure images are in the correct directory.")
            
    with col5:
        if st.button("→"):
            st.session_state.carousel_index = (st.session_state.carousel_index + 3) % len(images)


def main():
    # Initialize session state first
    initialize_session_state()
    
    # Sidebar for user details
    with st.sidebar:
        st.markdown("### User Details")
        name = st.text_input("Full Name *", value=st.session_state.name, key="name_input")
        email = st.text_input("Email ID *", value=st.session_state.email, key="email_input")
        mobile = st.text_input("Mobile Number (Optional)", value=st.session_state.mobile, key="mobile_input")
        
        # Save the values to session state
        st.session_state.name = name
        st.session_state.email = email
        st.session_state.mobile = mobile
    # Title and description with custom styling
    st.markdown('<h1 class="title">✈️ Bling Destinations</h1>', unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align: center; padding: 0 20px; margin-bottom: 2rem; color: #ffffff; font-weight: bold; font-size: 18px;">
            Your personal AI travel assistant. Get customized travel recommendations, itineraries, and answers to all your travel-related questions.
        </div>
    """, unsafe_allow_html=True)
    
    # Add the image carousel
    create_image_carousel()

    # Only show chat interface if email and name are provided
    if st.session_state.email.strip() and st.session_state.name.strip():
        # Chat container
        with st.container():
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            display_chat_history()
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Input field with Enter submission
        user_input = st.chat_input(
            placeholder="Type your message here...",
            key="user_input"
        )
        
        # Process user input when Enter is pressed
        if user_input:
            process_user_input(user_input)
            # Clear the input after processing
            st.rerun()
    else:
        st.info("Please enter your name and email address in the sidebar to start chatting.")

if __name__ == "__main__":
    main() 