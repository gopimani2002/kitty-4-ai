const BACKEND_URL = 'http://127.0.0.1:5000';

// --- DOM Elements ---
const appDiv = document.getElementById('app');
const loginPage = document.getElementById('login-page');
const chatPage = document.getElementById('chat-page');

// Login Elements
const nameInput = document.getElementById('name-input');
const continueWithNameButton = document.getElementById('continue-with-name-button');
const nameMessage = document.getElementById('name-message');

// Chat Elements
const loggedInUserSpan = document.getElementById('logged-in-user');
const newChatButton = document.getElementById('new-chat-button');
const logoutButton = document.getElementById('logout-button');
const activationInfo = document.getElementById('activation-info');
const chatHistoryDiv = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const microphoneButton = document.getElementById('microphone-button');
const voiceModeButton = document.getElementById('voice-mode-button');
const textModeButton = document.getElementById('text-mode-button');
const plusButton = document.getElementById('plus-button');

// --- Global State ---
let currentUser = null;
let isRecording = false;
let mediaRecorder;
let audioChunks = [];
let audioContext; // Declared globally to manage browser's audio context
let kittyAudioPlayer = null; // **CORRECTED:** Global variable for the AudioBufferSourceNode
let currentMode = 'voice'; // 'voice' or 'text' - starts in voice mode by default
let wakeModeActive = false; // Tracks the AI's activation state (synced with backend)

// --- Utility Functions ---
function showPage(pageId) {
    const allPages = document.querySelectorAll('.page');
    allPages.forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(pageId).classList.add('active');
}

function displayMessage(element, text, type = '') {
    element.textContent = text;
    element.className = 'message ' + type;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
    });
}

function appendMessage(sender, message) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('chat-message', sender);

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    contentDiv.textContent = message;
    messageDiv.appendChild(contentDiv);
    chatHistoryDiv.appendChild(messageDiv);

    scrollToBottom();
}

// **MODIFIED:** Correctly uses `stop()` and manages the global reference
async function playAudioFromBase64(base64Data, mimeType) {
    if (!base64Data) {
        console.warn("No audio data provided to playAudioFromBase64.");
        return;
    }
    
    // **CORRECTED:** Stop any existing playback before starting a new one
    stopCurrentPlayback();

    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    if (audioContext.state === 'suspended') {
        try {
            await audioContext.resume();
            console.log("AudioContext resumed successfully.");
        } catch (e) {
            console.error("Failed to resume AudioContext:", e);
        }
    }

    const audioBlob = b64toBlob(base64Data, mimeType);
    const arrayBuffer = await audioBlob.arrayBuffer();

    try {
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.start(0);

        // Store the AudioBufferSourceNode reference
        kittyAudioPlayer = source;
        source.onended = () => {
            console.log("Audio playback ended.");
            // Only clear the reference if the same source is still playing
            if (kittyAudioPlayer === source) {
                kittyAudioPlayer = null;
            }
        };
    } catch (error) {
        console.error("Error decoding or playing audio:", error);
    }
}

// **CORRECTED:** Function to stop the current audio playback
function stopCurrentPlayback() {
    if (kittyAudioPlayer) {
        // Correctly use `stop()` method for AudioBufferSourceNode
        kittyAudioPlayer.stop(); 
        kittyAudioPlayer = null;
        console.log("Audio playback interrupted.");
    }
}

function b64toBlob(b64Data, contentType = '', sliceSize = 512) {
    const byteCharacters = atob(b64Data);
    const byteArrays = [];

    for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
        const slice = byteCharacters.slice(offset, offset + sliceSize);
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }

    const blob = new Blob(byteArrays, { type: contentType });
    return blob;
}

function updateActivationInfo(isActive) {
    wakeModeActive = isActive;
    if (isActive) {
        activationInfo.textContent = "Kitty is active and listening!";
        activationInfo.className = 'info success';
        userInput.placeholder = "Ask Kitty...";
    } else {
        activationInfo.textContent = "Say 'Kitty' to activate me.";
        activationInfo.className = 'info';
        userInput.placeholder = "Say 'Kitty' to activate me.";
    }
}

function adjustInputHeight() {
    userInput.style.height = 'auto';
    userInput.style.height = userInput.scrollHeight + 'px';

    if (currentMode === 'voice') {
        if (userInput.value.trim().length > 0) {
            sendButton.style.display = 'flex';
            microphoneButton.style.display = 'none';
            plusButton.style.display = 'none';
        } else {
            sendButton.style.display = 'none';
            microphoneButton.style.display = 'flex';
            plusButton.style.display = 'flex';
        }
    } else {
        sendButton.style.display = 'flex';
        microphoneButton.style.display = 'none';
        plusButton.style.display = 'flex';
    }

    if (isRecording) {
        sendButton.style.display = 'none';
        plusButton.style.display = 'none';
        microphoneButton.style.display = 'flex';
    }
}

// --- API Calls ---
async function sendChatRequest(message, type = 'text', isInitialLoad = false) {
    if (!currentUser) {
        alert("Please log in first!");
        return { success: false, message: "User not logged in." };
    }

    let url = `${BACKEND_URL}/api/chat/${type}`;
    let options = {
        method: 'POST'
    };

    if (type === 'text') {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify({
            username: currentUser,
            message: message,
            responseMode: currentMode,
            isInitialLoad: isInitialLoad
        });
    } else if (type === 'audio') {
        const formData = new FormData();
        formData.append('username', currentUser);
        formData.append('audio', message, 'audio.webm');
        formData.append('responseMode', currentMode);
        options.body = formData;
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server responded with status ${response.status}: ${errorText}`);
        }
        const data = await response.json();

        if (data.success) {
            updateActivationInfo(data.wake_mode);

            if (data.response_text) {
                appendMessage('assistant', data.response_text);
            }

            if (currentMode === 'voice' && data.audio_data) {
                playAudioFromBase64(data.audio_data, data.audio_mime_type);
            }

            return data;
        } else {
            console.error("Backend error:", data.message);
            appendMessage('assistant', `Error: ${data.message}`);
            return { success: false, message: data.message };
        }
    } catch (error) {
        console.error("Error sending chat request:", error);
        appendMessage('assistant', "Network error: Couldn't connect to Kitty. Please check your connection or server status.");
        return { success: false, message: "Network error or backend unreachable." };
    }
}

// --- Login Logic ---
async function handleContinueWithName() {
    const name = nameInput.value.trim();
    if (!name) {
        displayMessage(nameMessage, "Please enter your name.", 'error');
        return;
    }

    continueWithNameButton.disabled = true;
    continueWithNameButton.textContent = 'Starting Chat...';

    try {
        const response = await fetch(`${BACKEND_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        });
        const data = await response.json();

        if (data.success) {
            currentUser = data.username;
            sessionStorage.setItem('username', currentUser);
            displayMessage(nameMessage, `Welcome, ${currentUser}!`, 'success');

            initChatPage();
            showPage('chat-page');

            await sendChatRequest("", "text", true);

        } else {
            displayMessage(nameMessage, data.message, 'error');
        }
    } catch (error) {
        console.error("Error with name login:", error);
        displayMessage(nameMessage, `Login error: ${error.message}.`, 'error');
    } finally {
        continueWithNameButton.disabled = false;
        continueWithNameButton.textContent = 'Start Chat';
    }
}

// --- Chat Page Logic ---
async function handleNewChat() {
    if (confirm("Are you sure you want to start a new chat? This will clear the current conversation.")) {
        chatHistoryDiv.innerHTML = '';
        stopCurrentPlayback();
        await resetBackendConversation(currentUser);
        updateActivationInfo(false);
        await sendChatRequest("", "text", true);
    }
}

async function handleLogout() {
    if (confirm("Are you sure you want to logout?")) {
        sessionStorage.removeItem('username');
        currentUser = null;
        chatHistoryDiv.innerHTML = '';
        stopCurrentPlayback();
        showPage('login-page');
        nameInput.value = '';
        displayMessage(nameMessage, '');
    }
}

async function handleSendText() {
    const message = userInput.value.trim();
    if (!message) return;
    
    // **CORRECTED:** Stop any playing audio when a new text message is sent
    stopCurrentPlayback();

    appendMessage('user', message);
    userInput.value = '';
    adjustInputHeight();

    await sendChatRequest(message, 'text');
}

// **MODIFIED:** Correctly implements the microphone state fix and stops audio
async function handleMicrophoneClick() {
    if (isRecording) {
        // **CORRECTED:** Stop audio if user interrupts with a new recording
        stopCurrentPlayback(); 
        mediaRecorder.stop();
    } else {
        // **CORRECTED:** Stop audio if user starts a new recording
        stopCurrentPlayback();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = [];

                appendMessage('user', "(Voice input...)");
                await sendChatRequest(audioBlob, 'audio');
                
                resetVoiceInputState();
            };

            mediaRecorder.start();
            microphoneButton.classList.add('recording');
            isRecording = true;
            userInput.placeholder = "Recording... Speak clearly.";
            userInput.disabled = true;
            sendButton.style.display = 'none';
            plusButton.style.display = 'none';
            microphoneButton.style.display = 'flex';
        } catch (error) {
            console.error("Error accessing microphone:", error);
            alert("Could not access microphone. Please allow microphone permissions and try again.");
            resetVoiceInputState();
        }
    }
}

function resetVoiceInputState() {
    isRecording = false;
    microphoneButton.classList.remove('recording');
    userInput.placeholder = "Ask Kitty...";
    userInput.disabled = false;
    adjustInputHeight();
}

async function resetBackendConversation(username) {
    try {
        const response = await fetch(`${BACKEND_URL}/api/reset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username })
        });
        const data = await response.json();
        if (!data.success) {
            console.error("Failed to reset backend conversation:", data.message);
        } else {
            console.log("Backend conversation reset successfully.");
            updateActivationInfo(false);
        }
    } catch (error) {
        console.error("Network error resetting backend conversation:", error);
    }
}

function setChatMode(mode) {
    currentMode = mode;
    voiceModeButton.classList.remove('active');
    textModeButton.classList.remove('active');

    if (currentMode === 'voice') {
        voiceModeButton.classList.add('active');
    } else {
        textModeButton.classList.add('active');
        userInput.placeholder = "Type your message...";
    }
    
    // **CORRECTED:** Stop any playing audio when the mode is switched
    stopCurrentPlayback();
    
    userInput.disabled = false;
    adjustInputHeight();
    updateActivationInfo(wakeModeActive);
}

function initChatPage() {
    loggedInUserSpan.textContent = `Logged in as: ${currentUser}`;
    updateActivationInfo(false);
    chatHistoryDiv.innerHTML = '';
    setChatMode('voice');
    userInput.value = '';
    adjustInputHeight();
}

// --- Event Listeners ---
continueWithNameButton.addEventListener('click', handleContinueWithName);
nameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        handleContinueWithName();
    }
});

newChatButton.addEventListener('click', handleNewChat);
logoutButton.addEventListener('click', handleLogout);

sendButton.addEventListener('click', handleSendText);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendText();
    }
});
userInput.addEventListener('input', adjustInputHeight);

microphoneButton.addEventListener('click', handleMicrophoneClick);
plusButton.addEventListener('click', () => {
    alert("Plus button clicked! (Future: upload file, insert image, etc.)");
});

voiceModeButton.addEventListener('click', () => setChatMode('voice'));
textModeButton.addEventListener('click', () => setChatMode('text'));


// --- Initialization on Load ---
document.addEventListener('DOMContentLoaded', () => {
    const storedUsername = sessionStorage.getItem('username');
    if (storedUsername) {
        currentUser = storedUsername;
        initChatPage();
        showPage('chat-page');
        sendChatRequest("", "text", true);
    } else {
        showPage('login-page');
    }

    const resumeAudioContext = () => {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (audioContext.state === 'suspended') {
            audioContext.resume().then(() => {
                console.log("AudioContext resumed by user interaction.");
                document.body.removeEventListener('click', resumeAudioContext);
                document.body.removeEventListener('touchend', resumeAudioContext);
            }).catch(e => console.error("Error resuming AudioContext on initial click:", e));
        } else {
            document.body.removeEventListener('click', resumeAudioContext);
            document.body.removeEventListener('touchend', resumeAudioContext);
        }
    };

    document.body.addEventListener('click', resumeAudioContext);
    document.body.addEventListener('touchend', resumeAudioContext);
});