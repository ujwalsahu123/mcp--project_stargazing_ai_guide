# StarGuide - AI-Powered Stargazing Assistant 🌟

An intelligent stargazing companion that combines Azure OpenAI GPT-4o with real astronomical calculations to provide live sky guidance through a beautiful ChatGPT-like web interface.

**What it does:** Enter your location → See top visible stars/planets → Ask questions → Get AI-powered insights with real sky data.

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites
- Python 3.10+
- Azure OpenAI API key (GPT-4o)
- Modern web browser

### Setup & Run

**Terminal 1: Backend Server**
```bash
cd Backend
uv sync
# Create .env with your Azure OpenAI key
echo "AZURE_OPENAI_KEY=your_key_here" > .env
echo "AZURE_OPENAI_ENDPOINT=your_endpoint_here" >> .env
uv run python main.py
# Runs on http://localhost:8000
```

**Terminal 2: Frontend Server**
```bash
cd Frontend
python -m http.server 5000
# Opens at http://localhost:5000
```

**3. Open browser:** http://localhost:5000 → Enter location → Enjoy! 🌌

---

## 🔄 How It All Works

### The Complete Flow

```
USER INTERFACE                  BACKEND LOGIC               ASTRONOMICAL DATA
─────────────────────────────────────────────────────────────────────────
Browser                          FastAPI                     MCP Server
(Port 5000)                       (Port 8000)                (Remote)
```

---

## 📤 Frontend → Backend Communication

### **STEP 1: User Enters Location**

**Frontend sends POST to `/initial`:**
```javascript
{
  "latitude": 19.074,           // Mumbai
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-20T20:30:00+05:30"  // ISO 8601 with timezone
}
```

**What happens:**
1. Frontend shows loading animation ("Generating...")
2. User interface is locked (input disabled)

---

### **STEP 2: Backend Processes Initial Request**

**Backend `/initial` endpoint does:**
1. ✓ Validates latitude (-90 to 90), longitude (-180 to 180)
2. ✓ Calls **MCP tool**: `visible_objects(lat, lon, time)`
   - Returns 26 visible objects from that location
   - Includes: name, altitude, azimuth, magnitude, distance
3. ✓ Sends top 10 objects to Azure OpenAI GPT-4o
4. ✓ LLM generates poetic intro (1-2 sentences) and descriptions (2-3 sentences each)
5. ✓ Returns **streaming response** (NDJSON format)

**Response stream format:**
```
{"type": "intro", "content": "Tonight, the sky above Mumbai is..."}
{"type": "object", "data": {"name": "Sirius", "magnitude": -1.46, ...}}
{"type": "object", "data": {"name": "Canopus", "magnitude": -0.74, ...}}
...
{"type": "complete", "total_objects_available": 26, "objects_returned": 10}
```

**Frontend processes stream:**
- Shows intro immediately (no waiting)
- Collects objects as they arrive
- Displays all objects when stream ends
- Re-enables input for chat

---

### **STEP 3: User Asks a Question**

**Frontend sends POST to `/chat`:**
```javascript
{
  "query": "Where is Venus right now?",
  "latitude": 19.074,
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-20T20:35:00+05:30",
  "chat_history": [
    {
      "role": "assistant",
      "content": "Tonight, the sky above Mumbai is...[intro text]"
    },
    {
      "role": "assistant", 
      "content": "[objects list]"
    },
    {
      "role": "user",
      "content": "Tell me about Sirius"
    },
    {
      "role": "assistant",
      "content": "Sirius is the brightest star..."
    }
  ]
}
```

---

### **STEP 4: Backend Processes Chat Query**

**Backend `/chat` endpoint does:**

1. **LLM receives:**
   - System prompt: "You are an astronomy AI. ALWAYS use tools for specific object data. Never reuse intro data."
   - User query: "Where is Venus?"
   - Chat history (full context)
   - Current time & location

2. **LLM analyzes and makes tool calls:**
   ```
   LLM thinks: "User asked about Venus position"
   LLM decides: Must call object_position and object_detail
   ```

3. **Backend calls MCP tools:**
   ```
   Tool 1: object_position("Venus", lat=19.074, lon=72.881, time=...)
   → Returns: {"altitude": 42.5, "azimuth": 215.3, "distance": "160M km"}
   
   Tool 2: object_detail("Venus")
   → Returns: {"type": "planet", "brightness": -4.7, "info": "Hottest planet..."}
   ```

4. **LLM receives tool results and generates response:**
   ```
   LLM now knows: exact position, details, brightness
   LLM generates: "Venus is currently at 42.5° altitude, 215.3° azimuth 
                   (SW direction). It's the brightest object..."
   ```

5. **Backend returns:**
   ```javascript
   {
     "success": true,
     "response": "Venus is currently at 42.5° altitude...",
     "tools_used": ["object_position", "object_detail"]
   }
   ```

**Frontend displays:**
- User question in right-aligned bubble (blue gradient)
- Loading animation (5-bar spectrum)
- AI response in left-aligned bubble (light gray)
- Continues accepting new questions

---

## 🔧 Backend Endpoints

### **POST /health**
Quick server check.
```bash
curl http://localhost:8000/health
→ {"status": "ok"}
```

### **POST /initial**
Get intro + top 10 visible objects.

**Request:**
```javascript
{
  "latitude": number,
  "longitude": number,
  "altitude": number,
  "time": "ISO-8601-string"
}
```

**Response (streaming NDJSON):**
```
{"type": "intro", "content": "..."}
{"type": "object", "data": {...}}
{"type": "complete", ...}
```

### **POST /chat**
Ask questions about the sky.

**Request:**
```javascript
{
  "query": "string",
  "latitude": number,
  "longitude": number,
  "altitude": number,
  "time": "ISO-8601-string",
  "chat_history": [{"role": "user|assistant", "content": "..."}]
}
```

**Response:**
```javascript
{
  "success": true,
  "response": "...",
  "tools_used": ["object_position", "object_detail"]
}
```

---

## 🛠️ MCP Tools (Astronomical Data)

Located at: **https://MCP-Project-Stargazing.fastmcp.app/mcp**

### **Tool 1: visible_objects**
Finds all visible celestial objects from a location/time.

**Parameters:**
```
latitude: float (-90 to 90)
longitude: float (-180 to 180)
observation_time: ISO-8601 timestamp
```

**Returns:**
```javascript
[
  {
    "name": "Sirius",
    "altitude": 45.2,        // angle above horizon (°)
    "azimuth": 180.5,        // compass direction (°)
    "magnitude": -1.46,      // brightness (lower = brighter)
    "distance": "8.6 ly",    // light-years
    "type": "star"
  },
  ...
]
```

### **Tool 2: object_position**
Gets exact altitude/azimuth for a specific object.

**Parameters:**
```
name: "Venus" | "Mars" | etc
latitude, longitude, observation_time
```

**Returns:**
```javascript
{
  "altitude": 42.5,
  "azimuth": 215.3,
  "visible": true,
  "distance": "160M km"
}
```

### **Tool 3: object_detail**
Gets detailed info about an object.

**Parameters:**
```
name: "Sirius" | "Jupiter" | etc
```

**Returns:**
```javascript
{
  "name": "Sirius",
  "type": "star",
  "magnitude": -1.46,
  "distance": "8.6 light-years",
  "constellation": "Canis Major",
  "mythology": "The Dog Star...",
  "brightness": "Brightest star in night sky"
}
```

---

## 💬 Chat History & Context

### How It Works:

**First interaction (just intro):**
```
Chat History = [
  {role: "assistant", content: "Intro text..."},
  {role: "assistant", content: "Objects list..."}
]
```

**After user asks a question:**
```
Chat History = [
  {role: "assistant", content: "Intro..."},
  {role: "assistant", content: "Objects..."},
  {role: "user", content: "Tell me about Sirius"},
  {role: "assistant", content: "Sirius is the brightest star..."}
]
```

**For next question:**
```
Chat History = [
  Previous messages...
  {role: "user", content: "Is Mars visible tonight?"},
  {role: "assistant", content: "Mars is at 35.2° altitude..."}
]
```

**Why this matters:**
- LLM has full conversation context
- Can answer "follow-up" questions ("What about it?" knows what "it" is)
- Prevents reusing stale intro data
- System prompt forces tool calls for fresh data

---

## 🎨 Frontend UI/UX

### **Components**

**Location Page:**
- Auto-detect geolocation button
- Manual latitude/longitude input
- "Start Stargazing" button
- Galactic header (75 animated stars)

**Chat Page:**
- Chat messages (user = blue, AI = gray)
- Premium spectrum analyzer loading (5 bars)
- Message history scrollable
- Input box (light gray) + arrow button (galaxy gradient)

### **Key Interactions**

1. **Typing query** → Input box shows light gray styling
2. **Click send button** → Button pulses with galaxy gradient
3. **Waiting for response** → Loading animation shows
4. **Response arrives** → Message appears in chat
5. **Continue asking** → Full history maintained

---

## 📁 File Structure

```
4_Project_StarGuide_MCP_AI_tool/
│
├── Frontend/
│   ├── index.html              # Single page structure
│   ├── script.js               # All JS logic (~300 lines)
│   ├── style.css               # Galactic styling (~1400 lines)
│   └── README.md
│
├── Backend/
│   ├── main.py                 # 3 API endpoints
│   ├── mcp_client.py           # Tool orchestration & LLM calls
│   ├── object_names.json       # 40+ celestial object names
│   ├── requirements.txt
│   └── README.md
│
├── MCP_Server/                 # (Remote - already deployed)
│   ├── main.py
│   ├── tools.py
│   ├── star_info.json
│   └── skyfield-data/
│
└── README.md                   # This file
```

---

## 🚀 API Example Walkthrough

### **Scenario: User in Mumbai asks about Venus**

**Frontend JavaScript:**
```javascript
// Step 1: User enters location and clicks "Start"
const response = await fetch('http://localhost:8000/initial', {
  method: 'POST',
  body: JSON.stringify({
    latitude: 19.074,
    longitude: 72.881,
    altitude: 0,
    time: "2026-04-20T20:30:00+05:30"
  })
});

// Step 2: User asks "Where is Venus?"
const chatResponse = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  body: JSON.stringify({
    query: "Where is Venus?",
    latitude: 19.074,
    longitude: 72.881,
    altitude: 0,
    time: "2026-04-20T20:35:00+05:30",
    chat_history: [
      {role: "assistant", content: "Intro..."},
      {role: "assistant", content: "Objects..."}
    ]
  })
});
```

**Backend Processing:**
```python
# Backend receives chat request
# LLM decides: "User asking about Venus" → need position & details

# Call MCP Tool 1: object_position
→ {"altitude": 42.5, "azimuth": 215.3}

# Call MCP Tool 2: object_detail  
→ {"magnitude": -4.7, "type": "planet", "info": "..."}

# LLM generates response using tool results
→ "Venus is at 42.5° altitude, WSW direction. It's the brightest..."
```

**Frontend Receives:**
```javascript
{
  "success": true,
  "response": "Venus is at 42.5° altitude...",
  "tools_used": ["object_position", "object_detail"]
}
```

---

## 🔑 Key Design Decisions

1. **Streaming Initial Response** - Shows intro immediately, doesn't wait for all objects
2. **Mandatory Tool Calling** - System prompt forces LLM to use fresh data, never reuses intro
3. **Full Chat History** - Every message stored, LLM has complete context
4. **Remote MCP Server** - Real astronomical calculations using Skyfield
5. **Minimal Frontend** - Pure vanilla JS, zero dependencies
6. **Galaxy Theme** - Purple/pink gradients, 75 animated stars

---

## 📝 Important Notes

- **MCP Endpoint:** https://MCP-Project-Stargazing.fastmcp.app/mcp
- **Time Format:** Always ISO-8601 with timezone (e.g., "2026-04-20T20:30:00+05:30")
- **Coordinates:** Latitude (-90 to 90), Longitude (-180 to 180)
- **Tool Calling:** Backend NEVER reuses intro data - always calls tools
- **Streaming:** Initial response streams line-by-line (NDJSON format)

---

## 🎯 What's Happening Behind the Scenes

When you ask "Where is Venus?":
1. Frontend sends query + full chat history to backend
2. Backend validates input
3. Backend sends query + history to OpenAI
4. OpenAI recognizes tool needed: `object_position`
5. Backend calls MCP: `object_position("Venus", lat, lon, time)`
6. MCP uses Skyfield to calculate exact position
7. Backend gets: altitude, azimuth, visibility
8. Backend sends tool result back to OpenAI
9. OpenAI generates human response using fresh data
10. Backend returns response to frontend
11. Frontend displays in chat bubble

**Total time: ~2-3 seconds** ⚡

---

## 🌟 Ready to Stargazing!

Start the backend and frontend servers, then explore the night sky with AI guidance. Happy stargazing! 🔭🌠
