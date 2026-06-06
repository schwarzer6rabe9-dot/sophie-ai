import { useState, useRef, useEffect } from "react"
import axios from "axios"

function OrbitRing({ radius, duration, color, size, offset = 0 }) {
  return (
    <div style={{
      position: "absolute", width: radius * 2, height: radius * 2,
      borderRadius: "50%", border: `1px solid ${color}`,
      opacity: 0.4, top: "50%", left: "50%",
      transform: "translate(-50%, -50%)",
    }}>
      <div style={{
        position: "absolute", width: size, height: size, borderRadius: "50%",
        background: color, boxShadow: `0 0 6px ${color}`,
        top: "50%", left: "50%", marginTop: -size/2, marginLeft: -radius - size/2,
        animation: `orbit ${duration}s linear infinite`,
        animationDelay: `${offset}s`,
        transformOrigin: `${radius + size/2}px ${size/2}px`
      }}/>
    </div>
  )
}

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [listening, setListening] = useState(false)
  const [started, setStarted] = useState(false)
  const [time, setTime] = useState(new Date())
  const [memSaved, setMemSaved] = useState(false)
  const audioRef = useRef(null)
  const recognitionRef = useRef(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const speak = async (text) => {
    try {
      setSpeaking(true)
      const response = await axios.post("https://sophie-ai-jfna.onrender.com/tts",
        { text }, { responseType: "blob" }
      )
      const url = URL.createObjectURL(response.data)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => setSpeaking(false)
      await audio.play()
    } catch (e) { setSpeaking(false) }
  }

  const checkForMemory = async (msg) => {
    const lower = msg.toLowerCase()
    if (lower.includes("merke dir") || lower.includes("vergiss nicht") || lower.includes("behalte")) {
      const fact = msg.replace(/merke dir[:\s]*/i, "").replace(/vergiss nicht[:\s]*/i, "").replace(/behalte[:\s]*/i, "").trim()
      if (fact) {
        await axios.post("https://sophie-ai-jfna.onrender.com/memory/add", { fact })
        setMemSaved(true)
        setTimeout(() => setMemSaved(false), 3000)
      }
    }
  }

  const sendMessage = async (text) => {
    const msg = text || input
    if (!msg.trim()) return
    await checkForMemory(msg)
    const userMsg = { role: "user", text: msg }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput("")
    setLoading(true)
    try {
      const response = await axios.post("https://sophie-ai-jfna.onrender.com/chat", {
        message: msg
      })
      const reply = response.data.reply
      setMessages([...newMessages, { role: "assistant", text: reply }])
      await speak(reply)
    } catch (e) {
      setMessages([...newMessages, { role: "assistant", text: "Fehler: " + e.message }])
    }
    setLoading(false)
  }

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return
    const recognition = new SpeechRecognition()
    recognition.lang = "de-DE"
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onstart = () => setListening(true)
    recognition.onresult = (e) => {
      setListening(false)
      sendMessage(e.results[0][0].transcript)
    }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
  }

  const handleStart = async () => {
    setStarted(true)
    try {
      const res = await axios.get("https://sophie-ai-jfna.onrender.com/briefing")
      const briefing = res.data.briefing
      setMessages([{ role: "assistant", text: briefing }])
      await speak(briefing)
    } catch (e) {
      const fallback = "System online. Hallo Antonio, ich bin Sophie. Bereit für deine Befehle."
      setMessages([{ role: "assistant", text: fallback }])
      await speak(fallback)
    }
  }

  const statusColor = speaking ? "#a78bfa" : listening ? "#f472b6" : "#00d4ff"

  if (!started) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "radial-gradient(ellipse at center, #0d1b2a 0%, #000510 100%)",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        fontFamily: "'Courier New', monospace", color: "#00d4ff", overflow: "hidden"
      }}>
        <style>{`@keyframes orbit { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        <div style={{ position: "relative", width: 260, height: 260, marginBottom: 40 }}>
          {[
            { r: 120, dur: 22, color: "rgba(0,212,255,0.4)", size: 5, off: 0 },
            { r: 96, dur: 15, color: "rgba(124,58,237,0.6)", size: 6, off: -4 },
            { r: 72, dur: 10, color: "rgba(0,212,255,0.5)", size: 4, off: -2 },
            { r: 50, dur: 6, color: "rgba(244,114,182,0.5)", size: 5, off: -1 },
          ].map((o, i) => <OrbitRing key={i} radius={o.r} duration={o.dur} color={o.color} size={o.size} offset={o.off}/>)}
          <div style={{
            position: "absolute", top: "50%", left: "50%",
            transform: "translate(-50%, -50%)",
            width: 70, height: 70, borderRadius: "50%",
            background: "radial-gradient(circle, rgba(0,212,255,0.15), transparent)",
            border: "2px solid #00d4ff", boxShadow: "0 0 25px rgba(0,212,255,0.3)",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          }}>
            <div style={{ fontSize: 10, letterSpacing: 2 }}>SOPHIE</div>
            <div style={{ fontSize: 7, color: "#7c3aed", letterSpacing: 1 }}>AI v2.0</div>
          </div>
        </div>
        <button onClick={handleStart} style={{
          padding: "12px 44px", background: "transparent",
          border: "1px solid #00d4ff", color: "#00d4ff",
          fontFamily: "Courier New", fontSize: 11, letterSpacing: 4, cursor: "pointer",
          boxShadow: "0 0 15px rgba(0,212,255,0.2)"
        }}>▶ SYSTEM STARTEN</button>
      </div>
    )
  }

  return (
    <div style={{
      height: "100vh", overflow: "hidden",
      background: "radial-gradient(ellipse at center, #0d1b2a 0%, #000510 100%)",
      display: "flex", flexDirection: "column",
      fontFamily: "'Courier New', monospace", color: "#00d4ff", position: "relative"
    }}>
      <style>{`
        @keyframes orbit { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:0.8;transform:translate(-50%,-50%) scale(1)}50%{opacity:1;transform:translate(-50%,-50%) scale(1.06)} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:translateY(0)} }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.15); }
      `}</style>
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(0,212,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.015) 1px, transparent 1px)",
        backgroundSize: "50px 50px"
      }}/>

      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "8px 24px", borderBottom: "1px solid rgba(0,212,255,0.1)",
        background: "rgba(0,0,0,0.3)", zIndex: 1, flexShrink: 0
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, boxShadow: `0 0 6px ${statusColor}` }}/>
          <span style={{ fontSize: 10, letterSpacing: 4 }}>SOPHIE AI</span>
        </div>
        <div style={{ fontSize: 10, color: "rgba(0,212,255,0.35)", letterSpacing: 3 }}>
          {time.toLocaleTimeString("de-DE")}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {memSaved && (
            <span style={{ fontSize: 8, color: "#a78bfa", letterSpacing: 2, animation: "fadeIn 0.3s ease" }}>
              ◉ GESPEICHERT
            </span>
          )}
          <div style={{ fontSize: 9, letterSpacing: 3, color: statusColor }}>
            {speaking ? "◉ SPRICHT" : listening ? "◉ HÖRT" : loading ? "◉ DENKT" : "◎ BEREIT"}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", zIndex: 1 }}>
        {/* Center Universe */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", position: "relative"
        }}>
          <div style={{ position: "relative", width: 280, height: 280 }}>
            {[
              { r: 130, dur: 25, color: "rgba(0,212,255,0.3)", size: 5, off: 0 },
              { r: 105, dur: 17, color: "rgba(124,58,237,0.5)", size: 7, off: -5 },
              { r: 80, dur: 11, color: "rgba(0,212,255,0.4)", size: 4, off: -2 },
              { r: 56, dur: 7, color: "rgba(244,114,182,0.5)", size: 5, off: -1 },
              { r: 36, dur: 4, color: "rgba(0,212,255,0.6)", size: 3, off: -3 },
            ].map((o, i) => <OrbitRing key={i} radius={o.r} duration={o.dur} color={o.color} size={o.size} offset={o.off}/>)}
            <div style={{
              position: "absolute", top: "50%", left: "50%",
              animation: "pulse 2.5s ease-in-out infinite",
              width: 64, height: 64, borderRadius: "50%",
              background: `radial-gradient(circle, ${speaking ? "rgba(167,139,250,0.25)" : "rgba(0,212,255,0.1)"}, transparent)`,
              border: `2px solid ${statusColor}`,
              boxShadow: `0 0 25px ${statusColor}50`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22
            }}>
              {listening ? "🎙" : speaking ? "🔊" : "✦"}
            </div>
          </div>
          <div style={{ textAlign: "center", marginTop: 16 }}>
            <div style={{ fontSize: 10, letterSpacing: 4, color: statusColor }}>SOPHIE</div>
            <div style={{ fontSize: 8, color: "rgba(0,212,255,0.3)", letterSpacing: 2, marginTop: 4 }}>
              {speaking ? "SPRICHT..." : listening ? "HÖRT ZU..." : loading ? "DENKT..." : "BEREIT"}
            </div>
          </div>
          <button onClick={startListening} disabled={listening || speaking} style={{
            marginTop: 20, width: 50, height: 50, borderRadius: "50%",
            background: listening ? "rgba(244,114,182,0.15)" : "rgba(0,212,255,0.05)",
            border: `2px solid ${listening ? "#f472b6" : "rgba(0,212,255,0.3)"}`,
            color: listening ? "#f472b6" : "#00d4ff",
            fontSize: 18, cursor: "pointer",
            boxShadow: listening ? "0 0 18px rgba(244,114,182,0.4)" : "0 0 8px rgba(0,212,255,0.1)"
          }}>🎙</button>
          <div style={{ marginTop: 12, fontSize: 8, color: "rgba(0,212,255,0.2)", letterSpacing: 2 }}>
            TIPP: "Merke dir: ..." zum Speichern
          </div>
        </div>

        {/* Right Log */}
        <div style={{
          width: 280, borderLeft: "1px solid rgba(0,212,255,0.08)",
          display: "flex", flexDirection: "column", padding: "12px 14px",
          background: "rgba(0,0,0,0.2)", flexShrink: 0
        }}>
          <div style={{ fontSize: 8, color: "rgba(0,212,255,0.25)", letterSpacing: 3, marginBottom: 10 }}>▸ LOG</div>
          <div style={{ flex: 1, overflowY: "auto", marginBottom: 10 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 7, color: "rgba(0,212,255,0.25)", letterSpacing: 2, marginBottom: 3 }}>
                  {m.role === "user" ? "▸ DU" : "▸ SOPHIE"}
                </div>
                <div style={{
                  fontSize: 11, lineHeight: 1.5,
                  color: m.role === "user" ? "rgba(196,181,253,0.7)" : "rgba(125,211,252,0.8)",
                  borderLeft: `2px solid ${m.role === "user" ? "rgba(124,58,237,0.3)" : "rgba(0,212,255,0.2)"}`,
                  paddingLeft: 8
                }}>{m.text}</div>
              </div>
            ))}
            <div ref={messagesEndRef}/>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage()}
              placeholder="Tippen..."
              style={{
                flex: 1, padding: "8px 10px",
                background: "rgba(0,212,255,0.03)",
                border: "1px solid rgba(0,212,255,0.15)",
                color: "#00d4ff", fontSize: 10, outline: "none",
                fontFamily: "Courier New"
              }}/>
            <button onClick={() => sendMessage()} disabled={loading} style={{
              padding: "8px 10px",
              background: "rgba(0,212,255,0.06)",
              border: "1px solid rgba(0,212,255,0.2)",
              color: "#00d4ff", fontSize: 10, cursor: "pointer",
              fontFamily: "Courier New"
            }}>▶</button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
