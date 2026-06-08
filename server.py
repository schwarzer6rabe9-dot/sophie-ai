from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import anthropic
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
load_dotenv()

from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
CORS(app)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "7eVMgwCnXydb3CikjV7a")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
JSONBIN_BIN = os.getenv("JSONBIN_BIN")
JSONBIN_KEY = os.getenv("JSONBIN_KEY")
MEMORY_FILE = "memory.json"
REDIRECT_URI = "https://sophie-ai-jfna.onrender.com/oauth/callback"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/calendar.readonly"]

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def load_memory():
    if JSONBIN_BIN and JSONBIN_KEY:
        try:
            r = requests.get(f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}/latest",headers={"X-Master-Key": JSONBIN_KEY})
            if r.status_code == 200:
                return r.json().get("record", {})
        except:
            pass
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_memory(memory):
    if JSONBIN_BIN and JSONBIN_KEY:
        try:
            requests.put(f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}",json=memory,headers={"X-Master-Key": JSONBIN_KEY,"Content-Type": "application/json"})
        except:
            pass
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

@app.route('/')
@app.route('/<path:path>')
def serve_index(path=''):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/health')
def health():
    return "OK", 200

@app.route('/briefing', methods=['GET'])
def briefing():
    return jsonify({"briefing": "System online. Hallo Antonio, ich bin Sophie. Bereit fuer deine Befehle."})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    memory = load_memory()
    facts = memory.get('facts', [])
    recent = memory.get('recent', [])[-5:]
    system_prompt = f"""Du bist Sophie, eine freundliche, intelligente KI-Assistentin. Du sprichst Deutsch und bist warm, empathisch und hilfsbereit.
Aktuelle Zeit: {datetime.now().strftime('%H:%M Uhr, %d.%m.%Y')}
Was du weisst: {'; '.join(facts) if facts else 'Noch nichts gespeichert.'}
Letzte Gespraeche: {'; '.join(recent) if recent else 'Keine.'}"""
    response = anthropic_client.messages.create(model="claude-sonnet-4-6",max_tokens=500,system=system_prompt,messages=[{"role": "user", "content": user_message}])
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

@app.route('/memory/add', methods=['POST'])
def memory_add():
    data = request.json
    fact = data.get('fact', '')
    memory = load_memory()
    if 'facts' not in memory:
        memory['facts'] = []
    memory['facts'].append(fact)
    save_memory(memory)
    return jsonify({"ok": True})

@app.route('/auth/google')
def auth_google():
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/gmail.readonly+https://www.googleapis.com/auth/calendar.readonly"
        "&access_type=offline"
        "&prompt=consent"
    )
    return jsonify({"auth_url": auth_url})

@app.route('/oauth/callback')
def oauth_callback():
    try:
        code = request.args.get('code')
        if not code:
            return "<h1>Fehler: Kein Code erhalten</h1>", 400
        token_response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        })
        token_data = token_response.json()
        if "error" in token_data:
            return f"<h1>Fehler: {token_data}</h1>", 500
        memory = load_memory()
        memory['google_token'] = {
            "token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        save_memory(memory)
        return "<h1>✅ Google verbunden! Sophie kann jetzt Gmail und Kalender lesen. Du kannst dieses Fenster schliessen.</h1>"
    except Exception as e:
        return f"<h1>Fehler: {str(e)}</h1>", 500

@app.route('/gmail/unread')
def gmail_unread():
    memory = load_memory()
    token_data = memory.get('google_token')
    if not token_data:
        return jsonify({"error": "Nicht verbunden"}), 401
    try:
        creds = Credentials(token=token_data['token'],refresh_token=token_data.get('refresh_token'),client_id=token_data['client_id'],client_secret=token_data['client_secret'],token_uri=token_data['token_uri'])
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(userId='me', labelIds=['UNREAD'], maxResults=5).execute()
        messages = results.get('messages', [])
        emails = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = {h['name']: h['value'] for h in m['payload']['headers']}
            emails.append({"from": headers.get('From'), "subject": headers.get('Subject')})
        return jsonify({"emails": emails})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug/routes')
def debug_routes():
    rules = [str(r) for r in app.url_map.iter_rules()]
    return jsonify({"routes": rules, "total": len(rules)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
