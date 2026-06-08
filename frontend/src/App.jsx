import { useState, useRef, useEffect } from "react"
import axios from "axios"

const API = "https://sophie-ai-jfna.onrender.com"

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [listening, setListening] = useState(false)
  const [started, setStarted] = useState(false)
  const [time, setTime] = useState(new Date())
  const [memSaved, setMemSaved] = useState(false)
  const [gmailConnected, setGmailConnected] = useState(false)
  const canvasRef = useRef(null)
  const audioRef = useRef(null)
  const recognitionRef = useRef(null)
  const messagesEndRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    if (started) {
      axios.get(`${API}/gmail/unread`).then(() => setGmailConnected(true)).catch(() => {})
    }
  }, [started])

  useEffect(() => {
    if (!started) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let W, H, t = 0

    const stars = Array.from({length: 220}, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random()*1.4+0.2,
      speed: Math.random()*0.00015+0.00003,
      op: Math.random()*0.7+0.2,
      tw: Math.random()*Math.PI*2
    }))

    const nebulas = [
      {x:0.15,y:0.2,r:190,c:'0,80,180'},
      {x:0.78,y:0.25,r:160,c:'70,20,150'},
      {x:0.5,y:0.65,r:210,c:'0,60,160'},
      {x:0.88,y:0.72,r:130,c:'90,0,170'},
    ]

    function resize() {
      W = canvas.width = canvas.offsetWidth
      H = canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    function draw() {
      t += 0.005
      ctx.fillStyle = '#00040e'
      ctx.fillRect(0,0,W,H)

      nebulas.forEach(n => {
        const g = ctx.createRadialGradient(n.x*W,n.y*H,0,n.x*W,n.y*H,n.r)
        g.addColorStop(0,`rgba(${n.c},0.07)`)
        g.addColorStop(1,`rgba(${n.c},0)`)
        ctx.fillStyle = g
        ctx.beginPath(); ctx.arc(n.x*W,n.y*H,n.r,0,Math.PI*2); ctx.fill()
      })

      const mx=W*0.82, my=H*0.17, mr=55
      const mg = ctx.createRadialGradient(mx-8,my-8,4,mx,my,mr*2.2)
      mg.addColorStop(0,'rgba(220,235,255,0.18)')
      mg.addColorStop(0.5,'rgba(160,190,255,0.07)')
      mg.addColorStop(1,'rgba(80,120,255,0)')
      ctx.fillStyle = mg
      ctx.beginPath(); ctx.arc(mx,my,mr*2.2,0,Math.PI*2); ctx.fill()
      ctx.beginPath(); ctx.arc(mx,my,mr,0,Math.PI*2)
      ctx.fillStyle = 'rgba(200,220,255,0.08)'
      ctx.strokeStyle = 'rgba(200,220,255,0.15)'
      ctx.lineWidth = 1; ctx.fill(); ctx.stroke()

      stars.forEach(s => {
        s.tw += 0.018
        const op = s.op*(0.5+0.5*Math.sin(s.tw))
        ctx.beginPath(); ctx.arc(s.x*W,s.y*H,s.r,0,Math.PI*2)
        ctx.fillStyle = `rgba(220,235,255,${op})`; ctx.fill()
        s.y += s.speed; if(s.y>1){s.y=0;s.x=Math.random()}
      })

      const cx=W*0.5, cy=H*0.42
      const orbits = [
        {r:48,speed:0.7,size:5,col:'150,210,255'},
        {r:70,speed:-0.45,size:6.5,col:'160,120,255'},
        {r:93,speed:0.3,size:4,col:'150,210,255'},
      ]
      orbits.forEach((o,i) => {
        const angle = t*o.speed+i*2.1
        const px = cx+Math.cos(angle)*o.r
        const py = cy+Math.sin(angle)*o.r
        ctx.beginPath(); ctx.arc(px,py,o.size,0,Math.PI*2)
        ctx.fillStyle = `rgba(${o.col},0.9)`
        ctx.shadowBlur=12; ctx.shadowColor=`rgba(${o.col},0.7)`
        ctx.fill(); ctx.shadowBlur=0
      })

      animRef.current = requestAnimationFrame(draw)
    }
    draw()
    return () => {
      cancelAnimationFrame(animRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [started])

  const speak = async (text) => {
    try {
      setSpeaking(true)
      const response = await axios.post(`${API}/tts`, { text }, { responseType: "blob" })
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
      const fact = msg.replace(/merke dir[:\s]*/i,"").replace(/vergiss nicht[:\s]*/i,"").replace(/behalte[:\s]*/i,"").trim()
      if (fact) {
        await axios.post(`${API}/memory/add`, { fact })
        setMemSaved(true)
        setTimeout(() => setMemSaved(false), 3000)
      }
    }
  }

  const checkGmail = async () => {
    try {
      const res = await axios.get(`${API}/gmail/unread`)
      const emails = res.data.emails || []
      if (emails.length === 0) return "Du hast keine ungelesenen Emails."
      const list = emails.map(e => `Von: ${e.from} | Betreff: ${e.subject}`).join("\n")
      return `Du hast ${emails.length} ungelesene Email(s):\n${list}`
    } catch (e) { return "Gmail nicht verbunden." }
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
      const lower = msg.toLowerCase()
      if (lower.includes("email") || lower.includes("mail") || lower.includes("postfach")) {
        const emailInfo = await checkGmail()
        const response = await axios.post(`${API}/chat`, { message: `Nutzer fragt nach Emails: ${emailInfo}. Antworte auf Deutsch freundlich.` })
        const reply = response.data.reply
        setMessages([...newMessages, { role: "assistant", text: reply }])
        setGmailConnected(true)
        await speak(reply)
      } else {
        const response = await axios.post(`${API}/chat`, { message: msg })
        const reply = response.data.reply
        setMessages([...newMessages, { role: "assistant", text: reply }])
        await speak(reply)
      }
    } catch (e) {
      setMessages([...newMessages, { role: "assistant", text: "Fehler: " + e.message }])
    }
    setLoading(false)
  }

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.lang = "de-DE"; r.continuous = false; r.interimResults = false
    r.onstart = () => setListening(true)
    r.onresult = (e) => { setListening(false); sendMessage(e.results[0][0].transcript) }
    r.onerror = () => setListening(false)
    r.onend = () => setListening(false)
    recognitionRef.current = r; r.start()
  }

  const handleStart = async () => {
    setStarted(true)
    try {
      const res = await axios.get(`${API}/briefing`)
      const briefing = res.data.briefing
      setMessages([{ role: "assistant", text: briefing }])
      await speak(briefing)
    } catch (e) {
      const fallback = "System online. Hallo Antonio, ich bin Sophie. Bereit fuer deine Befehle."
      setMessages([{ role: "assistant", text: fallback }])
      await speak(fallback)
    }
  }

  const connectGmail = () => {
    fetch(`${API}/auth/google`).then(r=>r.json()).then(d=>window.open(d.auth_url,'_self'))
  }

  const statusText = speaking ? "SPRICHT..." : listening ? "HOERT ZU..." : loading ? "DENKT..." : "BEREIT"

  const btnStyle = (type) => {
    const base = { padding:"7px 18px", borderRadius:"22px", fontFamily:"'Courier New',monospace", fontSize:"10px", letterSpacing:"2px", cursor:"pointer", fontWeight:"bold", border:"1px solid" }
    if (type==="green") return {...base, borderColor:"rgba(0,255,150,0.5)", background:"rgba(0,220,130,0.12)", color:"#b0ffe0"}
    if (type==="purple") return {...base, borderColor:"rgba(180,120,255,0.5)", background:"rgba(160,100,255,0.12)", color:"#ddc0ff"}
    return {...base, borderColor:"rgba(150,200,255,0.5)", background:"rgba(100,170,255,0.15)", color:"#e0f0ff"}
  }

  if (!started) {
    return (
      <div style={{minHeight:"100vh", background:"#00040e", fontFamily:"'Courier New',monospace", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:"40px", overflow:"hidden", position:"relative"}}>
        <style>{`@keyframes orbit{from{transform:rotate(0deg)}to{transform:rotate(360deg)}} @keyframes corepulse{0%,100%{box-shadow:0 0 20px rgba(150,200,255,0.3)}50%{box-shadow:0 0 45px rgba(150,200,255,0.6)}}`}</style>
        <div style={{position:"relative", width:"200px", height:"200px"}}>
          {[[96,"rgba(200,230,255,0.25)"],[140,"rgba(180,200,255,0.15)"],[186,"rgba(160,190,255,0.1)"]].map(([s,c],i) => (
            <div key={i} style={{position:"absolute",top:"50%",left:"50%",width:s,height:s,borderRadius:"50%",border:`1px solid ${c}`,transform:"translate(-50%,-50%)"}}/>
          ))}
          <div style={{position:"absolute",top:"50%",left:"50%",transform:"translate(-50%,-50%)",width:"68px",height:"68px",borderRadius:"50%",border:"2px solid rgba(200,230,255,0.8)",background:"radial-gradient(circle,rgba(150,200,255,0.15),transparent)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"26px",animation:"corepulse 3s ease-in-out infinite",color:"#fff"}}>✦</div>
        </div>
        <div style={{textAlign:"center"}}>
          <div style={{fontSize:"15px",letterSpacing:"6px",color:"#ffffff",fontWeight:"bold",textShadow:"0 0 15px rgba(150,210,255,0.9)"}}>SOPHIE</div>
          <div style={{fontSize:"10px",letterSpacing:"3px",color:"rgba(200,230,255,0.6)",marginTop:"5px"}}>AI v2.0 · PERSONAL ASSISTANT</div>
        </div>
        <button onClick={handleStart} style={{padding:"14px 50px",background:"transparent",border:"1px solid rgba(200,230,255,0.5)",color:"#ffffff",fontFamily:"Courier New",fontSize:"12px",letterSpacing:"5px",cursor:"pointer",borderRadius:"30px",fontWeight:"bold",textShadow:"0 0 10px rgba(150,210,255,0.8)"}}>
          SYSTEM STARTEN
        </button>
      </div>
    )
  }

  return (
    <div style={{minHeight:"100vh", background:"#00040e", fontFamily:"'Courier New',monospace", color:"#fff", overflow:"hidden", position:"relative"}}>
      <canvas ref={canvasRef} style={{position:"absolute",top:0,left:0,width:"100%",height:"100%"}}/>
      <style>{`@keyframes orbit{from{transform:rotate(0deg)}to{transform:rotate(360deg)}} @keyframes corepulse{0%,100%{box-shadow:0 0 20px rgba(150,200,255,0.3)}50%{box-shadow:0 0 45px rgba(150,200,255,0.6)}}`}</style>
      <div style={{position:"relative",zIndex:10,minHeight:"100vh",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"space-between",padding:"16px"}}>

        <div style={{width:"100%",display:"flex",justifyContent:"space-between",alignItems:"center",padding:"8px 20px",background:"rgba(0,0,0,0.45)",borderRadius:"30px",border:"1px solid rgba(180,220,255,0.18)",backdropFilter:"blur(12px)"}}>
          <div style={{fontSize:"12px",letterSpacing:"4px",color:"#ffffff",fontWeight:"bold",textShadow:"0 0 10px rgba(150,210,255,0.8)"}}>SOPHIE AI</div>
          <div style={{fontSize:"12px",letterSpacing:"2px",color:"rgba(220,240,255,0.7)"}}>{time.toLocaleTimeString("de-DE")}</div>
          <div style={{fontSize:"10px",letterSpacing:"2px",color:"rgba(180,230,255,0.65)"}}>{memSaved ? "GESPEICHERT" : statusText}</div>
        </div>

        <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:"14px",flex:1,justifyContent:"center"}}>
          <div style={{position:"relative",width:"200px",height:"200px"}}>
            {[[96,"rgba(200,230,255,0.25)"],[140,"rgba(180,200,255,0.15)"],[186,"rgba(160,190,255,0.1)"]].map(([s,c],i) => (
              <div key={i} style={{position:"absolute",top:"50%",left:"50%",width:s,height:s,borderRadius:"50%",border:`1px solid ${c}`,transform:"translate(-50%,-50%)"}}/>
            ))}
            <div style={{position:"absolute",top:"50%",left:"50%",transform:"translate(-50%,-50%)",width:"68px",height:"68px",borderRadius:"50%",border:"2px solid rgba(200,230,255,0.8)",background:"radial-gradient(circle,rgba(150,200,255,0.15),transparent)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"26px",animation:"corepulse 3s ease-in-out infinite",color:"#fff"}}>
              {listening?"🎙":speaking?"🔊":"✦"}
            </div>
          </div>
          <div style={{textAlign:"center"}}>
            <div style={{fontSize:"15px",letterSpacing:"6px",color:"#ffffff",fontWeight:"bold",textShadow:"0 0 15px rgba(150,210,255,0.9)"}}>SOPHIE</div>
            <div style={{fontSize:"10px",letterSpacing:"3px",color:"rgba(200,230,255,0.6)",marginTop:"5px"}}>{statusText}</div>
          </div>
        </div>

        <div style={{width:"100%",display:"flex",flexDirection:"column",gap:"10px",alignItems:"center"}}>
          <div style={{display:"flex",gap:"10px",justifyContent:"center",flexWrap:"wrap",alignItems:"center"}}>
            <button onClick={connectGmail} style={btnStyle("green")}>{gmailConnected?"✓ GMAIL":"GMAIL"}</button>
            <button style={btnStyle("blue")}>MEMORY</button>
            <button style={btnStyle("purple")}>KALENDER</button>
            <button style={btnStyle("blue")}>SETTINGS</button>
            <button onClick={startListening} style={{width:"54px",height:"54px",borderRadius:"50%",border:"2px solid rgba(200,230,255,0.55)",background:listening?"rgba(244,114,182,0.2)":"rgba(150,200,255,0.1)",color:"#fff",fontSize:"22px",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}>🎙</button>
          </div>
          <div style={{width:"100%",maxWidth:"520px",background:"rgba(0,5,20,0.6)",border:"1px solid rgba(180,220,255,0.18)",borderRadius:"18px",backdropFilter:"blur(14px)",overflow:"hidden"}}>
            <div style={{padding:"10px 14px",maxHeight:"100px",overflowY:"auto",fontSize:"11px",lineHeight:"1.7"}}>
              {messages.map((m,i) => (
                <div key={i} style={{color:m.role==="user"?"rgba(200,180,255,0.9)":"rgba(180,230,255,0.9)",whiteSpace:"pre-wrap"}}>
                  {m.role==="user"?"DU: ":"SOPHIE: "}{m.text}
                </div>
              ))}
              <div ref={messagesEndRef}/>
            </div>
            <div style={{display:"flex",borderTop:"1px solid rgba(180,220,255,0.12)"}}>
              <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&sendMessage()} placeholder="Schreib Sophie etwas..." style={{flex:1,padding:"10px 14px",background:"transparent",border:"none",color:"#ffffff",fontSize:"11px",fontFamily:"'Courier New',monospace",outline:"none"}}/>
              <button onClick={()=>sendMessage()} style={{padding:"10px 16px",background:"rgba(150,200,255,0.1)",border:"none",borderLeft:"1px solid rgba(180,220,255,0.12)",color:"#e0f0ff",cursor:"pointer",fontSize:"13px"}}>▶</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
