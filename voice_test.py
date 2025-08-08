import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
from datetime import datetime
import uuid
import os
import re
import time

# ✅ Detect if text contains Tamil characters
def is_tamil(text):
    return bool(re.search('[\u0B80-\u0BFF]', text))

# 🗣 Speak using gTTS with correct language
def speak(text):
    print("Kitty says:", text)

    if is_tamil(text):
        tts = gTTS(text=text, lang='ta')
    else:
        tts = gTTS(text=text, lang='en')

    filename = f"voice_{uuid.uuid4()}.mp3"
    tts.save(filename)
    playsound(filename)
    os.remove(filename)

# 🎤 Listen from microphone
def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Speak now...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)

    try:
        print("🔍 Recognizing...")
        query = recognizer.recognize_google(audio)
        print("You said:", query)
        return query
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that.")
        return ""
    except sr.RequestError:
        speak("Speech service is not available.")
        return ""

# 🚀 Main loop
if __name__ == "__main__":
    while True:
        query = listen()
        if query:
            is_tamil_input = is_tamil(query)

            if query.isascii():
                query = query.lower()

            if "stop" in query or "நிறுத்து" in query:
                speak("வணக்கம்! பார்ப்போம் பிறகு." if is_tamil_input else "Goodbye! See you soon.")
                break

            elif "hello" in query or "வணக்கம்" in query:
                speak("வணக்கம் கோபி! நான் கிட்டி. எப்படி உதவ வேண்டும்?" if is_tamil_input else "Hello Gopi! I’m Kitty. How can I help you?")

            elif "name" in query or "பெயர்" in query:
                speak("நான் உங்கள் உதவியாளர் கிட்டி." if is_tamil_input else "I am your assistant, Kitty.")

            elif "how are you" in query or "நீங்கள் எப்படி இருக்கிறீர்கள்" in query:
                speak("நான் நன்றாக இருக்கிறேன்! நீங்கள்?" if is_tamil_input else "I'm doing great! How about you ?")

            elif "time" in query or "நேரம்" in query:
                now = datetime.now().strftime("%I:%M %p")
                speak(f"தற்போதைய நேரம் {now}" if is_tamil_input else f"The current time is {now}")

            else:
                speak(query)  # Just echo back what user said

        time.sleep(1)
        
    