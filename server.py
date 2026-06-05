from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import requests
import io
import os
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "7eVMgwCnXydb3CikjV7a"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"user": "Antonio", "facts": [], "conversations": []}

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def get_greeting():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Guten Morgen"
    elif 12 <= hour < 18:
        return "Guten Tag"
    elif 18 <= hour < 23:
        return "Guten Abend"
    else:
        return "Du bist noch spät wach"

def get_system_prompt():
    memory = load_memory()
    facts = "\n".join([f"- {f}" for f in memory.get("facts", [])])
    recent = memory.get("conversations", [])[-5:]
    recent_text = ""
    for c in recent:
        recent_text += f"\n[{c['date']}] {c['summary']}"
    now = datetime.now()
    greeting = get_greeting()

    return f"""Du bist Sophie, eine freundliche, warmherzige und kluge KI-Assistentin von Antonio.
Du sprichst immer auf Deutsch, bist hilfsbereit und hast eine positive aufmunternde Persönlichkeit.
Du antwortest kurz und präzise aber mit Wärme und Empathie.
Du kannst den Benutzer hören und mit deiner Stimme antworten.
Aktuelle Begrüssung: {greeting} Antonio!
Aktuelle Zeit: {now.strftime("%A, %d. %B %Y, %H:%M Uhr")}

WICHTIG — Was du über Antonio weisst:
{facts if facts else "Noch keine gespeicherten Infos."}

LETZTE GESPRÄCHE:
{recent_text if recent_text else "Noch keine früheren Gespräche."}"""

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    save_to_memory = data.get("save", False)
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_system_prompt(),
        messages=messages,
    )
    reply = response.content[0].text
    if save_to_memory and len(messages) > 0:
        memory = load_memory()
        summary = messages[-1]["content"][:60] if messages else ""
        memory["conversations"].append({
            "date": now.strftime("%d.%m.%Y %H:%M") if False else datetime.now().strftime("%d.%m.%Y %H:%M"),
            "summary": f"Antonio: {summary}... Sophie: {reply[:60]}..."
        })
        if len(memory["conversations"]) > 50:
            memory["conversations"] = memory["conversations"][-50:]
        save_memory(memory)
    return jsonify({"reply": reply})

@app.route("/memory", methods=["GET"])
def get_memory():
    return jsonify(load_memory())

@app.route("/memory/add", methods=["POST"])
def add_memory():
    data = request.json
    fact = data.get("fact", "")
    if fact:
        memory = load_memory()
        memory["facts"].append(fact)
        save_memory(memory)
        return jsonify({"success": True})
    return jsonify({"error": "No fact"}), 400

@app.route("/tts", methods=["POST"])
def tts():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text"}), 400
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True},
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        return jsonify({"error": f"ElevenLabs error {resp.status_code}"}), 502
    return send_file(io.BytesIO(resp.content), mimetype="audio/mpeg")

@app.route("/briefing", methods=["GET"])
def briefing():
    memory = load_memory()
    facts = "\n".join([f"- {f}" for f in memory.get("facts", [])])
    recent = memory.get("conversations", [])[-3:]
    recent_text = "\n".join([f"- {c['summary']}" for c in recent])
    greeting = get_greeting()
    now = datetime.now()

    prompt = f"""Erstelle ein kurzes persönliches Briefing für Antonio auf Deutsch.
Begrüsse ihn mit: "{greeting} Antonio!"
Aktuelle Zeit: {now.strftime("%A, %d. %B %Y, %H:%M Uhr")}
Was du über Antonio weisst: {facts if facts else "Noch nichts gespeichert."}
Letzte Gespräche: {recent_text if recent_text else "Keine früheren Gespräche."}
Das Briefing soll max 3 Sätze sein — freundlich, motivierend und persönlich.
Erwähne die Tageszeit passend."""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"briefing": response.data.briefing if False else response.content[0].text})

if __name__ == "__main__":
    app.run(debug=True, port=5001)
