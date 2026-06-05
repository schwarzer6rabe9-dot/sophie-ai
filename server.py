from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import anthropic
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
CORS(app)

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "7eVMgwCnXydb3CikjV7a"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"facts": [], "recent": []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f)

@app.route('/')
def serve_index():
    return send_from_directory('frontend/dist', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join('frontend/dist', path)):
        return send_from_directory('frontend/dist', path)
    return send_from_directory('frontend/dist', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    memory = load_memory()
    facts = memory.get('facts', [])
    recent = memory.get('recent', [])[-5:]
    system_prompt = f"""Du bist Sophie, eine freundliche, intelligente KI-Assistentin.
Du sprichst Deutsch und bist warm, empathisch und hilfsbereit.
Aktuelle Zeit: {datetime.now().strftime('%H:%M Uhr, %d.%m.%Y')}
Was du weisst: {', '.join(facts) if facts else 'Noch nichts gespeichert.'}
Letzte Gespräche: {'; '.join(recent) if recent else 'Keine.'}"""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    reply = response.content[0].text
    recent.append(f"User: {user_message} | Sophie: {reply[:50]}")
    memory['recent'] = recent[-10:]
    save_memory(memory)
    return jsonify({"reply": reply})

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        audio_path = "/tmp/speech.mp3"
        with open(audio_path, 'wb') as f:
            f.write(response.content)
        return send_file(audio_path, mimetype='audio/mpeg')
    return jsonify({"error": "TTS failed"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)

@app.route("/health")
def health():
    return "OK", 200

