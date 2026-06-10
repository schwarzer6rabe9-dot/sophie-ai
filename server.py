from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import anthropic
import requests
import os
import json
from datetime import datetime
from pytz import timezone
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

import threading
import time as time_module

def auto_summary_job():
    last_save_hour = -1
    while True:
        try:
            now = datetime.now(timezone('Europe/Zurich'))
            current_hour = now.hour
            if current_hour == 22 and now.minute == 0:
                memory = load_memory()
                recent = memory.get('recent', [])
                today = now.strftime('%d.%m.%Y')
                already = any(s.get('date') == today for s in memory.get('summaries', []))
                if recent and not already:
                    response = anthropic_client.messages.create(
                        model='claude-sonnet-4-6',
                        max_tokens=300,
                        system='Fasse die folgenden Gespraeche in 3-5 Saetzen auf Deutsch zusammen. Nur die wichtigsten Infos behalten.',
                        messages=[{'role': 'user', 'content': str(recent)}])
                    summary_text = response.content[0].text
                    summaries = memory.get('summaries', [])
                    summaries.append({'date': today, 'summary': summary_text})
                    memory['summaries'] = summaries[-30:]
                    memory['recent'] = []
                    save_memory(memory)
                    print('[MEMORY] Auto-summary saved',flush=True)
            if current_hour % 4 == 2 and now.minute == 0 and current_hour != last_save_hour:
                last_save_hour = current_hour
                memory = load_memory()
                if memory:
                    save_memory(memory)
                    print(f'[MEMORY] Auto-save at {current_hour}:00',flush=True)
            time_module.sleep(60)
        except Exception as e:
            print(f'[MEMORY] Job error: {e}',flush=True)
            time_module.sleep(60)
summary_thread = threading.Thread(target=auto_summary_job, daemon=True)
summary_thread.start()

def load_memory():
    if JSONBIN_BIN and JSONBIN_KEY:
        try:
            r = requests.get(f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}/latest",headers={"X-Master-Key": JSONBIN_KEY},timeout=5)
            if r.status_code == 200:
                data = r.json().get("record", {})
                print(f"[MEMORY] Loaded: {len(data.get('recent',[]))} recent, {len(data.get('facts',[]))} facts",flush=True)
                return data
            else:
                print(f"[MEMORY] JSONBin load error: {r.status_code}",flush=True)
        except Exception as e:
            print(f"[MEMORY] JSONBin load failed: {e}",flush=True)
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_memory(memory):
    if JSONBIN_BIN and JSONBIN_KEY:
        try:
            r = requests.put(f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}",json=memory,headers={"X-Master-Key": JSONBIN_KEY,"Content-Type": "application/json"},timeout=5)
            print(f"[MEMORY] Saved to JSONBin: {r.status_code}",flush=True)
        except Exception as e:
            print(f"[MEMORY] JSONBin save failed: {e}",flush=True)
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
    try:
        from pytz import timezone
        now = datetime.now(timezone('Europe/Zurich'))
        hour = now.hour
        if hour < 12:
            gruss = 'Guten Morgen'
        elif hour < 18:
            gruss = 'Guten Tag'
        else:
            gruss = 'Guten Abend'
        time_str = now.strftime('%H:%M Uhr')
        weather_text = ''
        try:
            memory_loc = load_memory().get('location')
            if memory_loc:
                loc = f"{memory_loc['lat']},{memory_loc['lon']}"
            else:
                loc = 'Riffenmatt'
            w = requests.get(f'https://wttr.in/{loc}?format=%t+%C&m&lang=de', timeout=5)
            if w.status_code == 200:
                weather_text = f'Das Wetter in Riffenmatt: {w.text.strip()}.'
        except:
            weather_text = ''
        memory = load_memory()
        token_data = memory.get('google_token')
        email_text = ''
        if token_data:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                creds = Credentials(token=token_data["token"],refresh_token=token_data.get("refresh_token"),client_id=token_data["client_id"],client_secret=token_data["client_secret"],token_uri=token_data["token_uri"])
                service = build("gmail", "v1", credentials=creds)
                results = service.users().messages().list(userId="me", labelIds=["UNREAD"], maxResults=3).execute()
                messages = results.get("messages", [])
                if messages:
                    email_text = f"Du hast {len(messages)} ungelesene Emails."
                else:
                    email_text = "Keine ungelesenen Emails."
            except:
                email_text = ""
        parts = [p for p in [weather_text, email_text] if p]
        extra = " ".join(parts)
        briefing_text = f"{gruss} Antonio! Es ist {time_str}. {extra} Was liegt heute an?"
        return jsonify({"briefing": briefing_text})
    except Exception as e:
        return jsonify({"briefing": "Hallo Antonio! Ich bin Sophie, deine persoenliche Assistentin. Was kann ich heute fuer dich tun?"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    memory = load_memory()
    facts = memory.get('facts', [])
    recent = memory.get('recent', [])[-5:]
    summaries = memory.get('summaries', [])[-7:]
    summary_text = ' | '.join([s['date']+': '+s['summary'] for s in summaries]) if summaries else 'Keine.'
    system_prompt = f"""Du bist Sophie, eine freundliche, intelligente KI-Assistentin von Antonio. Du erkennst automatisch ob der Nutzer Deutsch oder Spanisch schreibt und antwortest IMMER in der gleichen Sprache. Bist du auf Deutsch angesprochen → antworte Deutsch. Bist du auf Spanisch angesprochen → antworte Spanisch. Du bist warm, empathisch und hilfsbereit.
Aktuelle Zeit: {datetime.now(timezone('Europe/Zurich')).strftime('%H:%M Uhr, %d.%m.%Y')}
Was du weisst: {'; '.join(facts) if facts else 'Noch nichts gespeichert.'}
Zusammenfassungen letzte 7 Tage: {summary_text}
Letzte Gespraeche: {'; '.join(recent) if recent else 'Keine.'}"""
    response = anthropic_client.messages.create(model="claude-sonnet-4-6",max_tokens=300,system=system_prompt,messages=[{"role": "user", "content": user_message}])
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


@app.route('/elevenlabs/usage', methods=['GET'])
def elevenlabs_usage():
    try:
        if not ELEVENLABS_API_KEY:
            return jsonify({'error': 'No API key'}), 400
        r = requests.get('https://api.elevenlabs.io/v1/user/subscription',
            headers={'xi-api-key': ELEVENLABS_API_KEY}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            used = data.get('character_count', 0)
            limit = data.get('character_limit', 100000)
            remaining = limit - used
            percent = round((used / limit) * 100, 1) if limit > 0 else 0
            return jsonify({'used': used, 'limit': limit, 'remaining': remaining, 'percent': percent})
        return jsonify({'error': f'ElevenLabs API error: {r.status_code}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/memory/add', methods=['POST'])
def memory_add():
    data = request.json
    fact = data.get('fact', '')
    memory = load_memory()
    if 'facts' not in memory:
        memory['facts'] = []
    if fact not in memory['facts']:
        memory['facts'].append(fact)
    memory['facts'] = memory['facts'][-50:]
    save_memory(memory)
    return jsonify({"ok": True})

@app.route('/memory/summary', methods=['POST'])
def memory_summary():
    try:
        memory = load_memory()
        recent = memory.get('recent', [])
        if not recent:
            return jsonify({"ok": False, "msg": "Nichts zu zusammenfassen"})
        summaries = memory.get('summaries', [])
        today = datetime.now(timezone('Europe/Zurich')).strftime('%d.%m.%Y')
        already = any(s.get('date') == today for s in summaries)
        if already:
            return jsonify({"ok": False, "msg": "Heute schon zusammengefasst"})
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system="Fasse die folgenden Gespraeche in 3-5 Saetzen auf Deutsch zusammen. Nur die wichtigsten Infos behalten.",
            messages=[{"role": "user", "content": str(recent)}]
        )
        summary_text = response.content[0].text
        summaries.append({"date": today, "summary": summary_text})
        memory['summaries'] = summaries[-30:]
        memory['recent'] = []
        save_memory(memory)
        return jsonify({"ok": True, "summary": summary_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/memory/view', methods=['GET'])
def memory_view():
    memory = load_memory()
    return jsonify({
        "facts": memory.get('facts', []),
        "summaries": memory.get('summaries', []),
        "recent_count": len(memory.get('recent', []))
    })

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


@app.route("/n8n", methods=["POST"])
def n8n_webhook():
    try:
        data = request.json
        message = data.get("message", "")
        n8n_url = "https://meister6.app.n8n.cloud/webhook/12d2278a-f586-477d-95f6-fd126747c042"
        response = requests.post(n8n_url, json={"message": message}, timeout=10)
        if response.status_code == 200:
            return jsonify({"ok": True, "result": response.json()})
        return jsonify({"error": "n8n Fehler"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
