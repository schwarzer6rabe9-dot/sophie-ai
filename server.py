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
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
MEMORY_FILE = "memory.json"
REDIRECT_URI = "https://sophie.maravi-o.com/oauth/callback"
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

@app.route('/location', methods=['POST'])
def update_location():
    try:
        data = request.json or {}
        lat = data.get('lat')
        lon = data.get('lon')
        city = data.get('city', '')

        if not lat or not lon:
            return jsonify({"error": "lat/lon fehlt"}), 400

        # In Memory speichern
        current_memory = load_memory()
        current_memory['location'] = {
            'lat': lat,
            'lon': lon,
            'city': city,
            'updated': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        save_memory(current_memory)

        print(f"[LOCATION] Gespeichert: {lat}, {lon} ({city})", flush=True)
        return jsonify({"status": "ok", "location": f"{lat}, {lon}"})

    except Exception as e:
        print(f"[LOCATION] Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

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
                if memory_loc and memory_loc.get('city'):
                    ort_name = memory_loc.get('city')
                elif memory_loc:
                    ort_name = f"{memory_loc['lat']:.2f}, {memory_loc['lon']:.2f}"
                else:
                    ort_name = 'Riffenmatt'
                weather_text = f'Das Wetter bei dir ({ort_name}): {w.text.strip()}.'
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

SEARCH_KEYWORDS = ["suche", "search", "was ist", "aktuelle", "neueste"]

def tavily_search(query):
    if not TAVILY_API_KEY:
        return None
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 3},
            timeout=8
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            snippets = [f"- {res.get('title', '')}: {res.get('content', '')[:200]}" for res in results]
            print(f"[TAVILY] {len(snippets)} results for: {query[:60]}", flush=True)
            return "\n".join(snippets)
        print(f"[TAVILY] Error {r.status_code}", flush=True)
    except Exception as e:
        print(f"[TAVILY] Exception: {e}", flush=True)
    return None

# ── Workspace-Hilfsfunktionen ────────────────────────────────────────────────

WORKSPACE_DIR = os.path.expanduser("~/sophie-workspace")

def _safe_workspace_path(relative_path: str) -> str:
    """Gibt den absoluten Pfad zurück – oder wirft ValueError wenn ausserhalb des Workspace."""
    # Sicherstellen dass WORKSPACE_DIR existiert
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    # Canonicalize: verhindert ../../../etc/passwd-Tricks
    abs_path = os.path.realpath(os.path.join(WORKSPACE_DIR, relative_path))
    if not abs_path.startswith(os.path.realpath(WORKSPACE_DIR)):
        raise ValueError(f"Zugriff verweigert: '{relative_path}' liegt ausserhalb von ~/sophie-workspace")
    return abs_path

def list_workspace_files(subdir: str = "") -> dict:
    """Listet Dateien und Ordner im Workspace (oder in einem Unterordner)."""
    try:
        target = _safe_workspace_path(subdir)
        if not os.path.exists(target):
            return {"error": f"Ordner '{subdir or '/'}' existiert nicht"}
        items = []
        for name in sorted(os.listdir(target)):
            full = os.path.join(target, name)
            items.append({
                "name": name,
                "type": "ordner" if os.path.isdir(full) else "datei",
                "size": os.path.getsize(full) if os.path.isfile(full) else None
            })
        return {"pfad": subdir or "/", "eintraege": items, "anzahl": len(items)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Fehler beim Auflisten: {e}"}

def read_workspace_file(relative_path: str) -> dict:
    """Liest den Inhalt einer Datei im Workspace."""
    try:
        abs_path = _safe_workspace_path(relative_path)
        if not os.path.isfile(abs_path):
            return {"error": f"Datei '{relative_path}' nicht gefunden"}
        size = os.path.getsize(abs_path)
        if size > 100_000:
            return {"error": f"Datei zu gross ({size} Bytes). Max. 100 KB."}
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return {"pfad": relative_path, "inhalt": content, "groesse": size}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Fehler beim Lesen: {e}"}

def write_workspace_file(relative_path: str, content: str) -> dict:
    """Schreibt Text in eine Datei im Workspace (erstellt sie bei Bedarf)."""
    try:
        abs_path = _safe_workspace_path(relative_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"ok": True, "pfad": relative_path, "groesse": len(content)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Fehler beim Schreiben: {e}"}

# Tool-Definitionen für Claude (Anthropic Tool Use Format)
WORKSPACE_TOOLS = [
    {
        "name": "list_workspace_files",
        "description": "Listet alle Dateien und Unterordner im Workspace-Ordner ~/sophie-workspace (oder einem Unterordner davon). Nützlich wenn der Nutzer fragt welche Dateien vorhanden sind.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subdir": {
                    "type": "string",
                    "description": "Optionaler Unterordner (relativ zu ~/sophie-workspace). Leer lassen für den Root-Ordner."
                }
            },
            "required": []
        }
    },
    {
        "name": "read_workspace_file",
        "description": "Liest den Textinhalt einer Datei aus ~/sophie-workspace. Nützlich wenn der Nutzer den Inhalt einer Datei sehen oder bearbeiten möchte.",
        "input_schema": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Pfad zur Datei, relativ zu ~/sophie-workspace. Beispiel: 'notizen.txt' oder 'projekte/ideen.md'"
                }
            },
            "required": ["relative_path"]
        }
    },
    {
        "name": "write_workspace_file",
        "description": "Schreibt oder erstellt eine Datei in ~/sophie-workspace. Nützlich wenn der Nutzer eine Datei speichern, erstellen oder aktualisieren möchte.",
        "input_schema": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Pfad zur Datei, relativ zu ~/sophie-workspace. Beispiel: 'notizen.txt'"
                },
                "content": {
                    "type": "string",
                    "description": "Der Text-Inhalt der in die Datei geschrieben wird."
                }
            },
            "required": ["relative_path", "content"]
        }
    }
]

def execute_workspace_tool(tool_name: str, tool_input: dict) -> str:
    """Führt ein Workspace-Tool aus und gibt das Ergebnis als JSON-String zurück."""
    if tool_name == "list_workspace_files":
        result = list_workspace_files(tool_input.get("subdir", ""))
    elif tool_name == "read_workspace_file":
        result = read_workspace_file(tool_input.get("relative_path", ""))
    elif tool_name == "write_workspace_file":
        result = write_workspace_file(tool_input.get("relative_path", ""), tool_input.get("content", ""))
    else:
        result = {"error": f"Unbekanntes Tool: {tool_name}"}
    print(f"[TOOL] {tool_name}({tool_input}) → {str(result)[:120]}", flush=True)
    return json.dumps(result, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')

    # TikTok Skript Trigger
    msg_lower = user_message.lower()
    if any(x in msg_lower for x in ['video erstellen', 'tiktok skript', 'skript erstellen', 'mach ein video', 'erstell ein video']):
        # Thema aus der Nachricht extrahieren
        thema = user_message
        for trigger in ['video erstellen', 'tiktok skript', 'skript erstellen', 'mach ein video', 'erstell ein video', 'sophie,', 'sophie']:
            thema = thema.lower().replace(trigger, '').strip()
        if not thema or len(thema) < 3:
            thema = 'AI-Tipp des Tages'

        # Intern /tiktok/skript aufrufen
        import urllib.request
        import json as json_module
        req_data = json_module.dumps({'thema': thema}).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:5001/tiktok/skript',
            data=req_data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json_module.loads(resp.read())
        return jsonify({'reply': result.get('response', 'Skript erstellt!')})

    memory = load_memory()
    facts = memory.get('facts', [])
    recent = memory.get('recent', [])[-5:]
    summaries = memory.get('summaries', [])[-7:]
    summary_text = ' | '.join([s['date']+': '+s['summary'] for s in summaries]) if summaries else 'Keine.'
    search_context = ""
    if any(kw in user_message.lower() for kw in SEARCH_KEYWORDS):
        results = tavily_search(user_message)
        if results:
            search_context = f"\nAktuelle Websuche-Ergebnisse:\n{results}\n"

    system_prompt = f"""Du bist Sophie, eine freundliche, intelligente KI-Assistentin von Antonio. Du erkennst automatisch ob der Nutzer Deutsch oder Spanisch schreibt und antwortest IMMER in der gleichen Sprache. Bist du auf Deutsch angesprochen → antworte Deutsch. Bist du auf Spanisch angesprochen → antworte Spanisch. Du bist warm, empathisch und hilfsbereit.
Aktuelle Zeit: {datetime.now(timezone('Europe/Zurich')).strftime('%H:%M Uhr, %d.%m.%Y')}
Was du weisst: {'; '.join(facts) if facts else 'Noch nichts gespeichert.'}
Zusammenfassungen letzte 7 Tage: {summary_text}
Letzte Gespraeche: {'; '.join(recent) if recent else 'Keine.'}{search_context}
{f"=== DEIN AKTUELLER ARBEITSKONTEXT ==={chr(10)}{workspace_context}" if workspace_context else ''}
Du hast Zugriff auf den Workspace-Ordner ~/sophie-workspace. Benutze die bereitgestellten Tools um Dateien zu lesen, schreiben und auflisten wenn der Nutzer danach fragt."""

    # Agentic Loop: Claude kann Tools aufrufen, bis sie eine finale Antwort gibt
    messages = [{"role": "user", "content": user_message}]
    reply = ""
    for _ in range(5):  # max 5 Tool-Runden (Endlosschleife verhindern)
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=system_prompt,
            tools=WORKSPACE_TOOLS,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            # Claude will ein Tool aufrufen → ausführen und Ergebnis zurückschicken
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_result = execute_workspace_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })
            messages.append({"role": "user", "content": tool_results})
            # Nächste Runde
            continue

        # Finale Antwort (stop_reason == "end_turn" oder kein tool_use)
        for block in response.content:
            if hasattr(block, "text"):
                reply = block.text
                break
        break

    if not reply:
        reply = "Entschuldigung, ich konnte keine Antwort generieren."

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


@app.route('/heygen/create', methods=['POST'])
def heygen_create():
    if not HEYGEN_API_KEY:
        return jsonify({"error": "HEYGEN_API_KEY not set"}), 500
    data = request.json or {}
    script = data.get('script', '')
    avatar_id = data.get('avatar_id', 'default')
    if not script:
        return jsonify({"error": "script is required"}), 400
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": "1bd001e7e50f421d891986aad5158bc8"
                }
            }
        ],
        "dimension": {"width": 1280, "height": 720}
    }
    try:
        r = requests.post(
            "https://api.heygen.com/v2/video/generate",
            json=payload,
            headers={"X-Api-Key": HEYGEN_API_KEY, "Content-Type": "application/json"},
            timeout=30
        )
        print(f"[HEYGEN] Status: {r.status_code}", flush=True)
        if r.status_code in [200, 201]:
            result = r.json()
            video_id = result.get('data', {}).get('video_id') or result.get('video_id')
            return jsonify({"video_id": video_id, "raw": result})
        return jsonify({"error": f"HeyGen error {r.status_code}", "detail": r.text}), r.status_code
    except Exception as e:
        print(f"[HEYGEN] Exception: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route("/n8n", methods=["POST"])
def n8n_webhook():
    try:
        data = request.json
        message = data.get("message", "")
        n8n_url = "https://meister6.app.n8n.cloud/webhook/7e22723e-c709-49b2-b6fc-93b86e8ce59b"
        response = requests.post(n8n_url, json={"message": message, "trigger": "sophie"}, timeout=10)
        print(f"[N8N] Status: {response.status_code}, Body: {response.text[:100]}", flush=True)
        if response.status_code in [200, 201]:
            try:
                return jsonify({"ok": True, "result": response.json()})
            except:
                return jsonify({"ok": True, "result": response.text})
        return jsonify({"error": f"n8n status {response.status_code}"}), 500
    except Exception as e:
        print(f"[N8N] Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Keine Datei gefunden"}), 400

        file = request.files['file']
        user_message = request.form.get('message', 'Was siehst du auf diesem Bild? Beschreibe die Person oder den Inhalt detailliert auf Deutsch.')
        is_selfie = request.form.get('is_selfie', 'false') == 'true'

        if is_selfie:
            user_message = "Das ist ein Foto von Antonio, dem Benutzer. Beschreibe sein Aussehen detailliert (Haare, Bart, Gesicht, Kleidung, Ausdruck). Diese Beschreibung wird in sein Gedächtnis gespeichert."

        import base64
        file_data = file.read()
        file_b64 = base64.b64encode(file_data).decode('utf-8')
        mime_type = file.content_type or 'image/jpeg'

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        if mime_type.startswith('image/'):
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": file_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": user_message
                        }
                    ]
                }]
            )
            answer = response.content[0].text
            if is_selfie:
                # Gleich wie memory_add() — laden, anhängen, speichern
                memory_entry = f"Antonio's Aussehen (Foto vom {datetime.now().strftime('%d.%m.%Y')}): {answer}"
                try:
                    current_memory = load_memory()
                    if 'facts' not in current_memory:
                        current_memory['facts'] = []
                    current_memory['facts'].append(memory_entry)
                    save_memory(current_memory)
                    print(f"[UPLOAD] Selfie-Beschreibung in Memory gespeichert", flush=True)
                except Exception as mem_err:
                    print(f"[UPLOAD] Memory save error: {mem_err}", flush=True)
                answer = f"📸 Ich habe mir dein Aussehen gemerkt!\n\n{answer}\n\nDiese Beschreibung ist jetzt dauerhaft in meinem Gedächtnis gespeichert."
        else:
            answer = "Videos können aktuell noch nicht analysiert werden. Schick mir ein Foto!"

        return jsonify({"response": answer})

    except Exception as e:
        print(f"[UPLOAD] Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route('/tiktok/skript', methods=['POST'])
def tiktok_skript():
    try:
        data = request.json or {}
        thema = data.get('thema', 'AI-Tipp des Tages')

        # Claude schreibt das Skript
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Schreibe ein kurzes TikTok-Skript (30-60 Sekunden) auf Deutsch zum Thema: {thema}

Das Skript ist für Sophie - eine AI-Assistentin die AI/Tech-Tipps erklärt.
Stil: locker, unterhaltsam, direkt zum Punkt.
Format:
HOOK (erste 3 Sekunden, Aufmerksamkeit wecken)
INHALT (Hauptteil, konkreter Tipp)
CTA (Call to Action, z.B. "Folg mir für mehr AI-Tipps!")
Nur das Skript, keine Erklärungen drumherum."""
            }]
        )

        skript_text = response.content[0].text

        # In drafts/ speichern
        datum = datetime.now().strftime('%Y-%m-%d')
        import re
        thema_slug = re.sub(r'[^a-z0-9-]', '', thema.lower().replace(' ', '-'))[:30]
        dateiname = f"{datum}_{thema_slug}.md"
        workspace = os.environ.get('WORKSPACE_PATH', os.path.join(os.path.expanduser('~'), 'sophie-workspace'))
        dateipfad = os.path.join(workspace, 'tiktok-content', 'drafts', dateiname)

        with open(dateipfad, 'w', encoding='utf-8') as f:
            f.write(f"# TikTok Skript: {thema}\n")
            f.write(f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"Status: draft\n\n")
            f.write(skript_text)

        print(f"[TIKTOK] Skript gespeichert: {dateiname}", flush=True)
        return jsonify({
            "response": f"✅ Skript erstellt und gespeichert!\n\nDatei: {dateiname}\n\n{skript_text}",
            "dateiname": dateiname
        })

    except Exception as e:
        print(f"[TIKTOK] Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


def load_workspace_context():
    """Lädt TODO.md und JARVIS_ROADMAP.md beim Start in den globalen Kontext"""
    global workspace_context
    workspace_context = ""
    try:
        workspace = os.environ.get('WORKSPACE_PATH', os.path.join(os.path.expanduser('~'), 'sophie-workspace'))

        todo_path = os.path.join(workspace, 'notizen', 'TODO.md')
        roadmap_path = os.path.join(workspace, 'notizen', 'JARVIS_ROADMAP.md')

        context_parts = []

        if os.path.exists(todo_path):
            with open(todo_path, 'r', encoding='utf-8') as f:
                context_parts.append(f"=== AKTUELLE TODO-LISTE ===\n{f.read()}")
            print("[STARTUP] TODO.md geladen", flush=True)

        if os.path.exists(roadmap_path):
            with open(roadmap_path, 'r', encoding='utf-8') as f:
                context_parts.append(f"=== JARVIS ROADMAP ===\n{f.read()}")
            print("[STARTUP] JARVIS_ROADMAP.md geladen", flush=True)

        workspace_context = "\n\n".join(context_parts)
        print(f"[STARTUP] Workspace-Kontext geladen ({len(workspace_context)} Zeichen)", flush=True)

    except Exception as e:
        print(f"[STARTUP] Fehler beim Laden des Workspace-Kontexts: {e}", flush=True)
        workspace_context = ""

# Beim Start ausführen
workspace_context = ""
load_workspace_context()


@app.route('/heygen/looks', methods=['GET'])
def heygen_looks():
    try:
        heygen_key = os.environ.get('HEYGEN_API_KEY')
        response = requests.get('https://api.heygen.com/v1/avatar.list', headers={'X-Api-Key': heygen_key}, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
