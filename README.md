# Desktop Voice Companion

A feature-rich desktop assistant application built using Python and PyQt6. It features a custom, frameless, draggable floating widget overlay that stays on top of your windows and integrates with your system tray for quick accessibility.

## ✨ Features

- **Text-to-Speech (TTS):** Read text aloud using local system voices (`pyttsx3`). Supports custom text input or automatically capturing and reading highlighted/selected text on your screen.
- **Speech-to-Text (STT):** Record audio directly from your microphone using `sounddevice` and convert spoken words into text using Google Speech Recognition.
- **Voice Customization:** Switch between available system speech voices via an intuitive settings menu.
- **System Tray Integration:** Runs discreetly in the system tray with quick options to show/hide the assistant or quit the application.
- **Draggable Floating UI:** An always-on-top, beautifully styled floating logo widget that moves smoothly alongside its context menu.

---

## 🛠️ Tech Stack

- **Python 3.x**
- **PyQt6** (GUI & Window Management)
- **pyttsx3** (Text-to-Speech Engine)
- **SpeechRecognition & SoundDevice** (Audio recording and speech-to-text processing)
- **Pyperclip** (Clipboard management for screen text selection)

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/bharadwaj-pandaraboina/desktop-speech-assistant.git](https://github.com/bharadwaj-pandaraboina/desktop-speech-assistant.git)
   cd desktop-speech-assistant
