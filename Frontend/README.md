# StarGuide Frontend

A beautiful, responsive web interface for the StarGuide AI stargazing companion. Built with vanilla HTML, CSS, and JavaScript.

## 🌟 Features

### Two-Page Flow
1. **Location Setup Page** - Auto-detect or manually enter your observation location
2. **Chat Interface** - Ask questions about tonight's sky and get AI-powered responses

### Beautiful UI
- 🌌 **Galactic Theme** - Purple-to-cyan gradient backgrounds with animated starfield (75 stars per header)
- 🎨 **Modern Design** - ChatGPT-like centered chat interface with message bubbles
- ⚡ **Smooth Animations** - Premium loading animation with gradient spectrum analyzer
- 📱 **Fully Responsive** - Optimized for mobile (480px), tablet (768px), and desktop

### Interactive Features
- 📡 **Auto-Detect Geolocation** - One-click location detection
- 💬 **Real-time Chat** - Stream questions to StarGuide AI backend
- 📊 **Initial Objects Display** - Top 10 visible celestial objects with details
- 🤖 **Loading State** - Beautiful 5-bar spectrum analyzer animation with "Calculating top brightest objects" title
- ↩️ **Easy Navigation** - Back button to change location, Enter key to send messages

## 🛠️ Tech Stack

- **HTML5** - Semantic markup with 150 animated stars
- **CSS3** - Modern styling with gradients, animations, and media queries (no unused code)
- **JavaScript (Vanilla)** - No frameworks, pure ES6+ with async/await
- **Responsive** - Mobile-first design with breakpoints at 480px and 768px

## 📦 File Structure

```
Frontend/
├── index.html          # Main HTML structure
├── script.js          # JavaScript logic (~275 lines, cleaned)
├── style.css          # Styling (~1400 lines, optimized)
└── README.md          # This file
```

## 🚀 Quick Start

### Prerequisites
- Web browser (Chrome, Firefox, Safari, Edge)
- Backend running at `http://localhost:8000`

### Start Development Server

```bash
# Using Python's built-in server (port 5000)
python -m http.server 5000

# Or with Node.js http-server
npx http-server -p 5000

# Then open browser at:
http://localhost:5000
```

### Environment Configuration

The frontend connects to the backend at `http://localhost:8000`. To change this, edit `script.js`:

```javascript
const CONFIG = { API_ENDPOINT: 'http://localhost:8000' };
```

## 📋 How It Works

### Page 1 - Location Input
1. Enter latitude, longitude, optional altitude
2. Click "📡 Auto-Detect" for browser geolocation
3. Click "Start Stargazing" to proceed to chat

### Page 2 - Chat Interface
1. View intro text and top 10 visible objects
2. Ask questions about the sky in the input field
3. AI responds with astronomical insights using real-time tool calls
4. Use "←" button to return and change location

## 🎨 Design System

### Color Palette
- **Primary Gradient**: Purple (#0a0015) → Cyan (#004e92)
- **Text**: Dark gray (#1f2937)
- **Accents**: Blue (#0066cc), Red (#ff6b6b)
- **Background**: Light gray (#f8f8f8)
- **Loading Bars**: Red→Orange→Yellow→Green→Blue spectrum

### Key Components

#### Galactic Header
- Full-width gradient background with 15s animation shift
- 75 animated floating stars with 6s float animation
- Glowing title text with text-shadow effects
- Page-specific styling for location vs chat views

#### Chat Bubbles
- **User messages**: Accent background with 👤 avatar
- **AI messages**: Gray background with 🤖 avatar
- **Markdown support**: Bold text via `**text**` syntax
- **Auto-scrolling**: Latest message always visible
- **Formatted rendering**: Line breaks preserved with `<br>` tags

#### Premium Loading Animation
- **5 Gradient Bars**: Red→Orange→Yellow→Green→Blue sequence
- **Wave Motion**: Bars bounce up/down with staggered delays
- **Smooth Easing**: Cubic-bezier timing for natural motion
- **Title**: "Calculating top brightest objects" displayed above
- **Professional Feel**: Like Spotify music visualizer

## 🔌 API Endpoints

### POST /initial
Get initial stargazing session with intro and top visible objects.

**Request:**
```json
{
  "latitude": 19.074,
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-20T14:32:15+05:30"
}
```

**Response:**
```json
{
  "success": true,
  "intro": "Tonight, the Mumbai sky is a canvas...",
  "objects": [
    {
      "name": "Sirius",
      "magnitude": -1.46,
      "altitude": 45.5,
      "azimuth": 180.2,
      "info": "The brightest star in the night sky..."
    }
  ],
  "total_objects_available": 26,
  "objects_returned": 10
}
```

### POST /chat
Send a question and get AI response with tool results.

**Request:**
```json
{
  "query": "Where is Sirius?",
  "latitude": 19.074,
  "longitude": 72.881,
  "altitude": 0,
  "time": "2026-04-20T14:32:15+05:30",
  "chat_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response:**
```json
{
  "success": true,
  "response": "Sirius is currently visible at altitude 45.5° and azimuth 180.2°..."
}
```

## 📱 Responsive Breakpoints

- **Desktop** (>768px): Full featured layout, max-width 900px
- **Tablet** (480px-768px): Adjusted padding, smaller fonts, compact buttons
- **Mobile** (<480px): Optimized input fields, touch-friendly buttons

## ✨ Code Quality

**Frontend Cleanup:**
- ✅ Removed unused CSS classes (thinking-orb, dots-animated, colorful-spinner, etc.)
- ✅ Removed unused keyframe animations
- ✅ Removed unused JavaScript functions (updateLoadingText)
- ✅ Optimized file sizes (~1400 lines CSS, ~275 lines JS)
- ✅ Clean, maintainable code structure

**Best Practices:**
- Pure vanilla JavaScript (no dependencies)
- GPU-accelerated animations (transform, opacity)
- Semantic HTML with proper structure
- CSS Grid and Flexbox layouts
- Mobile-first responsive design

## 🎯 Performance Tips

1. **CSS Animations**: Use GPU acceleration for smooth 60fps
2. **Lazy Loading**: Stars are pure CSS (no image assets)
3. **Event Efficiency**: Single listeners with proper delegation
4. **DOM Optimization**: Minimal manipulation, batch updates
5. **Network**: Async/await for smooth loading states

## 🌐 Browser Support

| Browser | Support |
|---------|---------|
| Chrome  | ✅ Latest |
| Firefox | ✅ Latest |
| Safari  | ✅ Latest |
| Edge    | ✅ Latest |
| iOS Safari | ✅ Latest |
| Chrome Mobile | ✅ Latest |

## 📝 JavaScript Functions

### Page Control
- `autoDetectLocation()` - Browser geolocation API
- `validateLocation()` - Validate lat/lon/alt inputs
- `startStargazing()` - Initialize chat view with /initial endpoint
- `goBack()` - Return to location setup page

### Chat Management
- `sendMessage()` - Send query to /chat endpoint
- `addMessage(content, role)` - Display message in chat with markdown
- `getISOTime()` - Generate ISO 8601 timestamp with timezone

### Utilities
- `showStatus(msg, type)` - Display status messages
- DOM element caching for performance

## 🎓 Learning Resources

- **CSS Animations**: MDN - `@keyframes`, `animation` properties
- **Responsive Design**: Mobile-first breakpoints strategy
- **Geolocation API**: W3C Geolocation standard
- **Fetch API**: Modern async data fetching with ES6 async/await

## 🔗 Related Documentation

- **Backend**: See `../Backend/README.md`
- **MCP Server**: See `../MCP_Server/README.md`
- **Full Project**: See `../README.md`

## 📄 License

Part of the StarGuide MCP AI Tool project.

# Navigate to Frontend directory
cd Frontend

# Start a local server (Python)
python -m http.server 8080

# OR using Node.js
npx http-server

# Open browser
# http://localhost:8080
```

### Option 2: GitHub Pages Deployment

1. **Push to GitHub**
```bash
git add .
git commit -m "Add StarGuide frontend"
git push origin main
```

2. **Enable GitHub Pages**
   - Go to repository Settings
   - Scroll to "GitHub Pages"
   - Select "Deploy from a branch"
   - Choose "main" branch and "root /" folder
   - Save

3. **Access your site**
   - `https://your-username.github.io/repo-name`

### Option 3: Static Hosting

Deploy `Frontend/` folder to:
- **Netlify** - Drag & drop deployment
- **Vercel** - Connect GitHub repo
- **AWS S3** - Static website hosting
- **Firebase Hosting** - Fast, secure
- **GitHub Pages** - Free with GitHub

## 📖 Usage

### 1. Set Location & Time

**Option A: Manual Entry**
- Enter latitude (-90 to 90)
- Enter longitude (-180 to 180)
- Enter altitude (optional, in km)
- Enter observation time

**Option B: Auto-Detect**
- Click "📡 Auto-Detect Location" button
- Allow browser permission
- Location filled automatically

**Quick Actions:**
- "⏰ Use Current Time" - Sets to current date/time
- "🔄 Clear" - Resets all fields

### 2. Get Tonight's Sky

1. Click "Get Initial Stargazing" button
2. See top 10 visible objects with details:
   - **Name** - Object identifier
   - **Magnitude** - Brightness (lower = brighter)
   - **Altitude** - Angle above horizon (0-90°)
   - **Azimuth** - Direction (0-360°, where 0° = North)
   - **Info** - Detailed poetic description

### 3. Ask Questions

1. Type astronomy question in chat input
   - Examples:
     - "Is Jupiter visible?"
     - "How far is Mars?"
     - "What constellation is this?"
2. Press Enter or click "Send"
3. StarGuide responds with real-time data
4. Continue conversation - history is maintained

### 4. Configure API

1. Click "⚙️ API Configuration" to expand
2. Enter backend API endpoint (default: `http://localhost:8000`)
3. Click "🧪 Test API Connection"
4. See connection status

## 🌍 CORS & Backend Connection

### Local Development

The frontend makes API calls to the backend. By default:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

Backend must have CORS enabled (already configured in main.py).

### GitHub Pages Deployment

**Important:** GitHub Pages hosts on HTTPS, so your backend must also be HTTPS or support CORS from GitHub Pages URL.

**Solutions:**
1. **Use HTTPS backend** - Deploy backend to cloud with SSL
2. **Use CORS proxy** - Forward requests through CORS-enabled proxy
3. **Backend on same domain** - Use reverse proxy (Nginx, etc.)

**Example CORS Proxy (for testing):**
```
Frontend: https://your-username.github.io/starguide
↓
CORS Proxy: https://cors-proxy.example.com
↓
Backend: http://localhost:8000
```

Free CORS proxies (use with caution - privacy concerns):
- `https://cors-anywhere.herokuapp.com`
- `https://api.allorigins.win`

**Recommended:** Deploy backend to cloud service like Heroku, AWS, or Azure.

## 🎨 Customization

### Change Theme Colors

Edit `style.css` CSS variables:

```css
:root {
    --primary-color: #4f46e5;        /* Blue */
    --secondary-color: #10b981;      /* Green */
    --error-color: #ef4444;          /* Red */
    /* ... etc */
}
```

### Change Default API Endpoint

Edit `script.js`:
```javascript
const CONFIG = {
    API_ENDPOINT: 'https://your-backend.com',
};
```

### Modify Layout

Edit `index.html` sections to add/remove features.

## 🐛 Debugging

### Open Browser Console

Press `F12` → Console tab

### Debug Tools

```javascript
// View current state
window.StarGuideDebug.state

// Get chat history
window.StarGuideDebug.getHistory()

// Clear localStorage
window.StarGuideDebug.clearCache()
```

### Common Issues

**"Failed to fetch" or CORS errors**
- Backend not running
- CORS not enabled on backend
- Wrong API endpoint URL
- Frontend and backend on different domains

**"Invalid location" error**
- Latitude outside -90 to 90
- Longitude outside -180 to 180
- Missing fields

**"API Connection Failed"**
- Click "Test API Connection" in Configuration section
- Verify backend is running: `uv run python main.py`
- Check API endpoint URL

**Browser geolocation not working**
- Site must use HTTPS (GitHub Pages is HTTPS by default)
- Grant location permission when prompted
- Some browsers block geolocation on HTTP (localhost is exception)

## 📱 Responsive Design

Works on all screen sizes:
- 💻 Desktop (1200px+)
- 🖥️ Tablet (768px - 1199px)
- 📱 Mobile (< 768px)

Tested on:
- Chrome
- Firefox
- Safari
- Edge
- Mobile browsers

## 🚀 Deployment Examples

### GitHub Pages (Recommended for beginners)

```bash
# 1. Create/push to GitHub
git push origin main

# 2. Go to Settings → Pages
# 3. Select main branch
# 4. Site published at https://username.github.io/repo
```

### Netlify

```bash
# 1. Connect GitHub repo
# 2. Build command: (leave blank - static site)
# 3. Publish directory: Frontend/
# 4. Deploy
```

### Vercel

```bash
# 1. Push to GitHub
# 2. Go to vercel.com
# 3. New Project → Connect GitHub
# 4. Select repo
# 5. Deploy
```

### AWS S3 + CloudFront

```bash
# 1. Create S3 bucket
# 2. Upload Frontend/ files
# 3. Enable static website hosting
# 4. (Optional) Add CloudFront CDN
```

## 📋 Checklist

Before deploying:

- [ ] Backend API running and accessible
- [ ] CORS enabled on backend
- [ ] API endpoint URL configured correctly
- [ ] Location/time inputs validated
- [ ] Chat functionality tested
- [ ] Mobile responsiveness checked
- [ ] Browser console has no errors
- [ ] GitHub repo public (for Pages)

## 📞 Support

### Backend Issues
See [Backend README](../Backend/README.md)

### API Documentation
- Swagger UI: `{API_ENDPOINT}/docs`
- ReDoc: `{API_ENDPOINT}/redoc`

### Testing Backend
```bash
cd Backend
uv run python test3.py
```

## 📄 License

Part of StarGuide project © 2026

---

**Last Updated:** April 20, 2026
**Version:** 1.0.0
**Status:** Production Ready ✅
