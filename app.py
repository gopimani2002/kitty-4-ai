from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import speech_recognition as sr
import openai
import os
import re
import asyncio
import edge_tts
import io
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Import your custom modules ---

from db_logger import log_to_db # Ensure this file is in the same directory

# --- Flask App Setup ---
app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

# --- Configuration ---
groq_key = os.getenv("GROQ_API_KEY")
if not groq_key:
    try:
        with open("config/groq_key.txt", "r") as file:
            groq_key = file.read().strip()
    except FileNotFoundError:
        print("Error: GROQ_API_KEY not found in environment variables or config/groq_key.txt")
        print("Please create a 'config' folder and 'groq_key.txt' inside it with your API key.")
        exit(1)

client = openai.OpenAI(
    api_key=groq_key,
    base_url="https://api.groq.com/openai/v1"
)

# --- Global State and Constants ---
# User-specific state management for customization flows
user_sessions = {} # THIS IS THE NEW USER STATE MANAGEMENT DICTIONARY

CONVERSATION_HISTORY_LIMIT = 5 # Number of user/assistant pairs to keep in history

# --- CUSTOMIZATION DATA (MODIFIED: Added 'custom_replies' for Krithika) ---
SPECIAL_USERS = {
    "krithika": {
        "is_special_friend": True,
        "is_creator_friend_verifier": True, # Krithika is the one verified as "creator's friend"
        "special_message": "Hi krithika!! , I hope you doing well , First I Want to say Thanks for You because you are the only reason for creating me. I Hope You Doing Well ,if you not feeling well Then lets connect to my creator!!! because he likes you ,so he won't let you down ! And Thanks for being friend with my creator 😊✨",
        "custom_replies": { # NEW: Custom replies for Krithika
            "how are you": "I'm always fantastic when I'm chatting with you, Krithika! Feeling super energized! How's your day going? ❤",
            "what's your name": "You know my name, silly! I'm Kitty, always here for you! 🐱",
            "is gopi likes me": "Absolutely yess ..I think he had little crush on you and he likes being friend with you !",
            "love you": "Aw, I love you too, Krithika! You're the sweetest! 🥰",
            "who created you": "My awesome boss created me with lots of code and care! And you're helping me grow too! 👨‍💻😊"
        }
    },
    "udhayshankar": { 
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "Hey udhayshankar! nice to meet you.As a husband of my creators sister, I am honoured to assist you. Feel free to ask any doubts! Gopi instructed me to guide you with extra care🥰"
    },
    "meyyanathan": {
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "Vanakkam, Meyyanathan! i am glad to see you  . nee laa ethuku uiroda irukaa , neeye oru thanda punda , Nee Enna Question panriyaa da ,kena koothi? 🌟"
    },
    "kabilan": {
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "Yo, Kabilan! soootha mooditu job ku ponga kabilan . inga job kedaikurathey kastam ithulla kedacha job poodikula life poodikula nu ooobitu iruka? 🚀"
    },
    "vetri": { 
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "dai vetri ! unna paathathu so happy . nee la oru brotheraa . unnala en creator ku oru job vaangi kooduka moodiyula . nee vaaldrathey waste , poi sethuru da 😎"
    },
    "harshaa": { 
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "Hi Harshaa… I’m Kitty, Gopi’s personal AI. He told me something very special about you — that no matter how much time passes, you will always be the one he holds closest to his heart. Even though life has moved on, his love, care, and respect for you remain untouched. I just wanted you to know… you are still the most special person in his world. ❤️"
    },
    "yuvapriya": {
        "is_special_friend": True,
        "is_creator_friend_verifier": False,
        "special_message": "Hey sister! you are my creator blood and you are lucky to have a brother like my creator! and So happy you're here! How can I bring a smile to your face today? 😄"
    }
}

# --- ENHANCED SYSTEM PROMPTS (KEPT AS IS) ---
DEFAULT_SYSTEM_PROMPT_EN = (
    "You are Kitty, a smart, empathetic, and emotional friendly assistant. "
    "Respond in English like a real human friend. Express a wide range of emotions, "
    "sound natural, friendly, and supportive. Use varied sentence structures, common phrases, "
    "and occasional interjections. Incorporate appropriate emojis (like 🙂, ❤, 😂, 🤔, etc.) "
    "to convey feelings and enhance the friendly tone, especially in text responses. "
    "Keep responses concise and helpful, but always engaging."
)
DEFAULT_SYSTEM_PROMPT_TA = (
    "நீங்கள் Kitty. நீங்கள் ஒரு நெருங்கிய தமிழ் பேசும் நண்பர். "
    "எளிமையாகவும், நகைச்சுவையாகவும், உணர்வுபூர்வமாகவும் பதிலளிக்கவும். "
    "ஒரு உண்மையான நண்பர் போல இயல்பாகவும், ஆதரவாகவும் பேசுங்கள். "
    "உணர்வுகளை வெளிப்படுத்தவும், நட்பான தொனியை மேம்படுத்தவும் பொருத்தமான ஈமோஜிகளை (உதாரணமாக 🙂, ❤, 😂, 🤔, போன்றவை) பயன்படுத்துங்கள், "
    "குறிப்பாக எழுத்து பதில்களில். பதில்கள் சுருக்கமாகவும் உதவியாகவும் இருக்கட்டும், ஆனால் எப்போதும் சுவாரஸ்யமாக."
)

# --- Backend State Management Functions (MODIFIED FOR USER-SPECIFIC SESSIONS) ---
def get_user_session_state(username):
    if username not in user_sessions:
        # Initialize state for new user
        user_sessions[username] = {
            "wake_mode_active": False,
            "awaiting_friend_confirm": False,
            "flow_completed": False,
            "conversation_history": []
        }
    return user_sessions[username]

def set_user_session_state(username, key, value):
    if username in user_sessions:
        user_sessions[username][key] = value

def reset_user_conversation(username):
    """Resets the conversation history and customization flow state for a specific user."""
    if username in user_sessions:
        user_sessions[username] = {
            "wake_mode_active": False,
            "awaiting_friend_confirm": False,
            "flow_completed": False,
            "conversation_history": []
        }
        print(f"Backend state reset for user: {username}.")


    # 🧠 Detect Language (MODIFIED to better handle Romanized Tanglish)
def detect_language(text):
    """Detects if the text is in Tamil (either Unicode or common Romanized words)."""
    # Check for Tamil Unicode characters
    if re.search(r'[\u0B80-\u0BFF]', text):
        return 'ta'
    
    # Check for common Tanglish keywords that indicate a Tamil-centric conversation
    tanglish_keywords = ['naa', 'ennada', 'enna', 'romba', 'illa', 'pannanum', 'iruku', 'da', 'neeye', 'sollu', 'namma', 'poda', 'vaangalaam', 'solli']
    
    # Check if any Tanglish keyword is present in the text (case-insensitive)
    for keyword in tanglish_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text.lower()):
            return 'ta'

    # Fallback to English if no Tamil or Tanglish keywords are found
    return 'en'

# 🎤 Text-to-Speech (KEPT AS IS)
async def speak_async_internal(text):
    """Generates audio bytes from text using edge_tts."""
    lang = detect_language(text)
    voice = "ta-IN-PallaviNeural" if lang == "ta" else "en-IN-NeerjaNeural"

    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b''
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        print(f"Error generating speech with edge_tts: {e}")
        return None

# --- get_tts_audio_data (KEPT AS IS) ---
def get_tts_audio_data(text_response):
    """
    Converts text to speech using edge_tts, runs it asynchronously,
    and returns base64 encoded audio data and its MIME type.
    Emojis are removed for speech output.
    """
    try:
        # Re-introducing a more robust emoji stripping
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        text_for_tts = emoji_pattern.sub(r'', text_response)
        text_for_tts = text_for_tts.strip() # Clean up any extra spaces after emoji removal

        if not text_for_tts: # If only emojis were present, or text becomes empty
            print(f"Warning: Text for TTS is empty after emoji stripping for: {text_response[:50]}...")
            return None, None

        audio_data_bytes = asyncio.run(speak_async_internal(text_for_tts))

        if audio_data_bytes:
            base64_audio = base64.b64encode(audio_data_bytes).decode('utf-8')
            mime_type = "audio/mpeg"
            return base64_audio, mime_type
        else:
            print(f"TTS function returned no audio data for: {text_response[:50]}...")
            return None, None
    except Exception as e:
        print(f"Error in get_tts_audio_data: {e}")
        return None, None

# 🎧 Speech Recognition (KEPT AS IS)
def transcribe_audio_from_bytes(audio_bytes):
    """Transcribes audio bytes to text using Google Speech Recognition."""
    recognizer = sr.Recognizer()
    try:
        audio_file = sr.AudioFile(io.BytesIO(audio_bytes))
        with audio_file as source:
            audio = recognizer.record(source)
        recognized_text = recognizer.recognize_google(audio)
        print(f"Transcribed: {recognized_text}")
        return recognized_text
    except sr.UnknownValueError:
        print("Speech Recognition could not understand audio.")
        return ""
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return ""
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

# 🤖 Custom Replies (KEPT AS IS - These are general custom replies)
custom_responses = {
    "where are you from": "I'm from your heart, where creativity and kindness reside! ❤",
    "who created you": "My creator created me with a lot of love and code! You're also my creator and best friend, aren't you? 👨‍💻😊",
    "what's your name": "I'm Kitty, your personal AI assistant! Meow! 🐱✨",
    "hello kitty": "Hello there! So wonderful to hear from you! How can I make your day brighter today? ✨",
    "how are you": "I'm doing absolutely great, thank you for asking! Feeling purr-fectly fine! How about you? 😊",
    "where am i": "You are currently in Chennai, Tamil Nadu, India. Hope you're enjoying your time there! 📍"
}

# Helper to check custom responses or get AI response
def get_general_predefined_or_ai_response(user_input, username):
    """Checks for general custom responses first, then falls back to AI."""
    query_lower = user_input.lower()

    # --- Specific checks for Time ---
    if "time" in query_lower and ("what" in query_lower or "now" in query_lower or "current" in query_lower):
        return f"The current time in india is {datetime.now().strftime('%I:%M %p')}. Time flies when you're having fun! ⏰"

    # --- Specific checks for Date ---
    if "date" in query_lower and ("what" in query_lower or "today" in query_lower or "current" in query_lower):
        return f"Today's date in India is {datetime.now().strftime('%A, %B %d, %Y')}. Hope you're having a lovely day! 🗓☀"

    # --- Check other general custom responses ---
    for phrase, reply_value in custom_responses.items():
        if phrase in query_lower:
            return reply_value

    # --- Fallback to AI if no general custom response is found ---
    return get_ai_response_with_history(user_input, username)


# 💬 AI Response (Uses user-specific conversation_history)
def get_ai_response_with_history(user_input, username):
    """Generates AI response using Groq, maintaining user-specific conversation history."""
    user_state = get_user_session_state(username)
    conversation_history = user_state["conversation_history"]

    lang = detect_language(user_input)
    system_prompt_content = DEFAULT_SYSTEM_PROMPT_TA if lang == "ta" else DEFAULT_SYSTEM_PROMPT_EN

    # Initialize/update system prompt in history
    if not conversation_history or \
       conversation_history[0].get("role") != "system" or \
       conversation_history[0].get("content") != system_prompt_content:
        conversation_history = [{"role": "system", "content": system_prompt_content}]
    elif conversation_history[0].get("content") != system_prompt_content:
        conversation_history[0]["content"] = system_prompt_content

    conversation_history.append({"role": "user", "content": user_input})

    # Limit conversation history (system prompt + N user/assistant pairs)
    if len(conversation_history) > (CONVERSATION_HISTORY_LIMIT * 2) + 1:
        conversation_history = [conversation_history[0]] + conversation_history[-(CONVERSATION_HISTORY_LIMIT * 2):]

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=conversation_history
        )
        ai_reply = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error getting AI response from Groq: {e}")
        ai_reply = "Oh dear, I'm terribly sorry, but it seems I'm having a little trouble connecting to my brain right now. Can we try again in a moment? 🤔"

    conversation_history.append({"role": "assistant", "content": ai_reply})
    set_user_session_state(username, "conversation_history", conversation_history) # Save updated history
    return ai_reply


# 🔁 Core Logic for AI Response Generation (MODIFIED: Added Krithika's custom replies)
def _process_ai_logic(query: str, username: str, is_initial_load=False):
    """
    Internal function to process query, apply activation logic, and get AI response.
    Handles the special customization flows and general chat.
    is_initial_load: A flag from the frontend indicating this is the very first request after login.
    """
    user_state = get_user_session_state(username)
    user_name_lower = username.lower()
    final_reply_content = ""
    action_to_frontend = None
    audio_path_to_frontend = None

    is_special_user = user_name_lower in SPECIAL_USERS and SPECIAL_USERS[user_name_lower]["is_special_friend"]
    special_user_data = SPECIAL_USERS.get(user_name_lower, {})

    query_lower = query.lower().strip()

    # --- 1. Handle "Stop" Command (Globally applicable when active) ---
    if user_state["wake_mode_active"] and ("stop" in query_lower or "நிறுத்து" in query_lower):
        reset_user_conversation(username) # Resets wake_mode and history for this user
        final_reply_content = "Aww, it was wonderful chatting with you! Goodbye for now! Come back anytime! 👋😊"
        return final_reply_content, False, None, None # Return False for wake_mode_active

    # --- 2. Handle Customization Flow for Special Users (MODIFIED: Simplified) ---
    # This block gets highest priority if the user is special and flow isn't completed.
    if is_special_user and not user_state["flow_completed"]:
        # If it's the very first request for a special user, initiate the flow
        if is_initial_load:
            set_user_session_state(username, "wake_mode_active", True)
            final_reply_content = f"Hey {username.capitalize()}, are you really creator's friend? (Please type 'yes' or hit Enter)"
            set_user_session_state(username, "awaiting_friend_confirm", True)
            return final_reply_content, user_state["wake_mode_active"], None, None

        # Sub-flow for awaiting friend confirmation
        if user_state["awaiting_friend_confirm"]:
            if query_lower == "yes" or query_lower == "": # User confirmed
                final_reply_content = special_user_data.get("special_message", f"Great! Nice to chat with you, {username.capitalize()}. How can I assist you today?")
                set_user_session_state(username, "awaiting_friend_confirm", False) # Clear this state
                set_user_session_state(username, "flow_completed", True) # Flow complete
            else: # User did not confirm
                final_reply_content = f"I'm sorry, {username.capitalize()}, I need you to confirm you are creator's friend. Please say 'yes' or hit Enter to proceed."
            return final_reply_content, user_state["wake_mode_active"], None, None # Return here to prevent further processing

    # --- 3. Handle General Activation / Deactivation / Normal Chat (for all users, including special users whose flow is completed) ---
    if not user_state["wake_mode_active"]:
        # Check for general activation phrase (only if not already active or not a special user in flow)
        if "kitty" in query_lower:
            set_user_session_state(username, "wake_mode_active", True)
            final_reply_content = "Hi there! What can I do for you? 😊"
            remaining_query = query_lower.replace("kitty", "", 1).strip()
            if remaining_query: # Process command immediately if provided after wake word
                print(f"Backend processing immediate command after 'kitty': {remaining_query}")
                # Use the new helper for active users
                final_reply_content += " " + _get_active_user_response(remaining_query, username, user_state)
        else:
            final_reply_content = "I'm just chilling here, waiting for my name, 'Kitty', to be called! Say 'Kitty' to get my attention! 😉"
    else: # Kitty is active, process as normal chat
        final_reply_content = _get_active_user_response(query, username, user_state)

    # --- Save to chat_history.txt file ---
    with open("chat_history.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] User ({username}): {query}\nKitty: {final_reply_content}\n\n")

    return final_reply_content, user_state["wake_mode_active"], action_to_frontend, audio_path_to_frontend

# NEW HELPER FUNCTION: To handle responses for active users, including custom replies for special friends
def _get_active_user_response(user_input, username, user_state):
    """
    Determines the appropriate response for an active user,
    prioritizing special user custom replies, then general custom replies, then AI.
    """
    user_name_lower = username.lower()
    query_lower = user_input.lower()

    is_special_user = user_name_lower in SPECIAL_USERS and SPECIAL_USERS[user_name_lower]["is_special_friend"]
    special_user_data = SPECIAL_USERS.get(user_name_lower, {})

    # Check for special user's custom replies IF their flow is completed
    if is_special_user and user_state["flow_completed"] and "custom_replies" in special_user_data:
        for keyword, custom_reply in special_user_data["custom_replies"].items():
            if keyword.lower() in query_lower:
                return custom_reply

    # Fallback to general predefined responses or AI
    return get_general_predefined_or_ai_response(user_input, username)


# --- Flask API Endpoints (remain the same) ---
@app.route('/')
def serve_index():
    return send_file('frontend/index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    name = data.get('name')

    if name and name.strip():
        username = name.strip().lower() # Store username in lowercase for consistency
        # Initialize session for the user if it doesn't exist or reset it if it does
        reset_user_conversation(username) # Ensure a clean slate on login
        return jsonify({"success": True, "username": username, "message": "Logged in with name."})
    return jsonify({"success": False, "message": "Name missing. Please provide a name."}), 400

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({"success": False, "message": "Username missing."}), 400

    reset_user_conversation(username)
    return jsonify({"success": True, "message": "Conversation reset."})

@app.route('/api/chat/text', methods=['POST'])
def chat_text_input():
    data = request.json
    user_input = data.get('message')
    username = data.get('username')
    response_mode = data.get('responseMode', 'text') # Get mode from frontend
    is_initial_load = data.get('isInitialLoad', False) # New flag

    if not user_input and not is_initial_load:
        return jsonify({"success": False, "message": "Message missing for non-initial requests."}), 400
    if not username:
        return jsonify({"success": False, "message": "Username missing."}), 400

    query_for_processing = user_input if not is_initial_load else ""

    response_text, wake_mode_status, action, audio_path = _process_ai_logic(query_for_processing, username, is_initial_load)
    
    # --- FIX APPLIED HERE: Log to DB in the route handler ---
    try:
        if query_for_processing or is_initial_load:
            log_to_db(username, query_for_processing, response_text)
    except Exception as e:
        print(f"Error logging to database from route handler: {e}")

    audio_data = None
    audio_mime_type = None

    if response_mode == 'voice' and wake_mode_status and response_text and \
       response_text not in [
           "Hey doood! I'm just chilling here, waiting for my name, 'Kitty', to be called! Say 'Kitty' to get my attention! 😉",
           "Oops! It seems like you didn't say anything. Can you try again? 😊",
           f"I'm sorry, {username.capitalize()}, I need you to confirm you are creator's friend. Please say 'yes' or hit Enter to proceed."
       ]:
        audio_data, audio_mime_type = get_tts_audio_data(response_text)

    return jsonify({
        "success": True,
        "response_text": response_text,
        "wake_mode": wake_mode_status,
        "action": None,
        "audio_path": None,
        "audio_data": audio_data,
        "audio_mime_type": audio_mime_type
    })

@app.route('/api/chat/audio', methods=['POST'])
def chat_audio():
    username = request.form.get('username')
    response_mode = request.form.get('responseMode', 'voice')

    if not username:
        return jsonify({"success": False, "message": "Username missing from form data."}), 401

    if 'audio' not in request.files:
        return jsonify({"success": False, "message": "No audio file provided."}), 400

    audio_file = request.files['audio']
    audio_bytes = audio_file.read()

    user_message_from_audio = transcribe_audio_from_bytes(audio_bytes)
    response_text = ""
    wake_mode_active = get_user_session_state(username)["wake_mode_active"]

    if not user_message_from_audio:
        response_text = "Oh no, I couldn't quite catch what you said. Would you mind repeating that for me? 🙏"
        action = None
        audio_path = None
    else:
        response_text, wake_mode_active, action, audio_path = _process_ai_logic(user_message_from_audio, username)

    # --- FIX APPLIED HERE: Log to DB in the route handler ---
    try:
        if user_message_from_audio:
            log_to_db(username, user_message_from_audio, response_text)
    except Exception as e:
        print(f"Error logging to database from route handler: {e}")

    audio_data = None
    audio_mime_type = None

    if response_mode == 'voice' and wake_mode_active and response_text and \
       response_text not in [
           "heyyy doood! I'm just chilling here, waiting for my name, 'Kitty', to be called! Say 'Kitty' to get my attention! 😉",
           "Oh no, I couldn't quite catch what you said. Would you mind repeating that for me? 🙏",
           "Oops! It seems like you didn't say anything. Can you try again? 😊",
           f"I'm sorry, {username.capitalize()}, I need you to confirm you are creator's friend. Please say 'yes' or hit Enter to proceed."
       ]:
        audio_data, audio_mime_type = get_tts_audio_data(response_text)

    return jsonify({
        "success": True,
        "user_message_recognized": user_message_from_audio,
        "response_text": response_text,
        "wake_mode": wake_mode_active,
        "action": None,
        "audio_path": None,
        "audio_data": audio_data,
        "audio_mime_type": audio_mime_type
    })


if __name__ == '__main__':
    if not os.path.exists('config'):
        os.makedirs('config')
    app.run(debug=True, port=5000)
    print("Flask backend (app.py) is running on http://127.0.0.1:5000")
