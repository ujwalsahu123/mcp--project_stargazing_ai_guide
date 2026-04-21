const CONFIG = { API_ENDPOINT: 'http://localhost:8000' };

let state = {
    chatHistory: [],
    currentLocation: null,
};

const elements = {
    latitude: document.getElementById('latitude'),
    longitude: document.getElementById('longitude'),
    altitude: document.getElementById('altitude'),
    autoDetectBtn: document.getElementById('autoDetectBtn'),
    startBtn: document.getElementById('startBtn'),
    locationStatus: document.getElementById('locationStatus'),
    pageLocation: document.getElementById('page-location'),
    pageChat: document.getElementById('page-chat'),
    backBtn: document.getElementById('backBtn'),
    chatContainer: document.getElementById('chatContainer'),
    chatInput: document.getElementById('chatInput'),
    chatLoading: document.getElementById('chatLoading'),
    sendBtn: document.getElementById('sendBtn'),
};

document.addEventListener('DOMContentLoaded', () => {
    elements.autoDetectBtn.addEventListener('click', autoDetectLocation);
    elements.startBtn.addEventListener('click', startStargazing);
    elements.backBtn.addEventListener('click', goBack);
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });
});

function autoDetectLocation() {
    if (!navigator.geolocation) {
        showStatus('Geolocation not supported', 'error');
        return;
    }

    showStatus('Detecting location...', 'info');
    elements.autoDetectBtn.disabled = true;

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            elements.latitude.value = pos.coords.latitude.toFixed(6);
            elements.longitude.value = pos.coords.longitude.toFixed(6);
            showStatus('Location detected ✓', 'success');
            elements.autoDetectBtn.disabled = false;
        },
        (err) => {
            showStatus(err.message, 'error');
            elements.autoDetectBtn.disabled = false;
        }
    );
}

function validateLocation() {
    const lat = parseFloat(elements.latitude.value);
    const lon = parseFloat(elements.longitude.value);
    const alt = parseFloat(elements.altitude.value);

    if (isNaN(lat) || lat < -90 || lat > 90) {
        showStatus('Invalid latitude', 'error');
        return false;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
        showStatus('Invalid longitude', 'error');
        return false;
    }
    if (isNaN(alt) || alt < 0) {
        showStatus('Invalid altitude', 'error');
        return false;
    }
    return true;
}

async function startStargazing() {
    if (!validateLocation()) return;

    const lat = parseFloat(elements.latitude.value);
    const lon = parseFloat(elements.longitude.value);
    const alt = parseFloat(elements.altitude.value);
    const time = getISOTime();

    state.currentLocation = { lat, lon, alt };

    elements.pageLocation.classList.add('hidden');
    elements.pageChat.classList.remove('hidden');
    elements.chatContainer.innerHTML = '';
    state.chatHistory = [];

    // Show initial loading in the same stream where assistant messages appear.
    showChatLoading('Generating');
    elements.chatInput.disabled = true;
    elements.sendBtn.disabled = true;

    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/initial`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lon, altitude: alt, time }),
        });

        if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
        }

        hideChatLoading();
        const streamMessage = createStreamingAssistantMessage();
        let streamedInitialText = '';
        let objectCount = 0;

        await streamNdjson(response, (chunk) => {
            if (chunk.type === 'intro') {
                const intro = chunk.content || '';
                if (intro) {
                    streamedInitialText += `${intro}\n\n`;
                    streamMessage.append(`${intro}\n\n`);
                }
            } else if (chunk.type === 'object' && chunk.data) {
                const obj = chunk.data;
                objectCount += 1;
                if (objectCount === 1) {
                    const heading = '🌟 **Top Visible Objects Tonight:**\n\n';
                    streamedInitialText += heading;
                    streamMessage.append(heading);
                }
                const objectText = `${objectCount}. **${obj.name}**\n   Brightness: ${obj.magnitude} | Position: ${obj.altitude}° alt, ${obj.azimuth}° az\n   ${obj.info}\n\n`;
                streamedInitialText += objectText;
                streamMessage.append(objectText);
            }
        });

        if (!streamedInitialText.trim()) {
            streamedInitialText = 'Session started. Ask me what you want to explore in the sky.';
            streamMessage.append(streamedInitialText);
        }

        streamMessage.finalize();
        state.chatHistory.push({ role: 'assistant', content: streamedInitialText.trim() });

    } catch (error) {
        hideChatLoading();
        addMessage(`Error: ${error.message}`, 'error');
    } finally {
        hideChatLoading();
        elements.chatInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.chatInput.focus();
    }
}

async function sendMessage() {
    const query = elements.chatInput.value.trim();
    if (!query) return;

    if (!state.currentLocation) {
        addMessage('Location is not initialized. Please go back and start stargazing again.', 'error');
        return;
    }

    const lat = state.currentLocation.lat;
    const lon = state.currentLocation.lon;
    const alt = state.currentLocation.alt;
    const time = getISOTime();

    addMessage(query, 'user');
    elements.chatInput.value = '';

    state.chatHistory.push({ role: 'user', content: query });

    const pendingAssistant = createStreamingAssistantMessage(true);
    elements.chatInput.disabled = true;
    elements.sendBtn.disabled = true;

    try {
        const response = await fetch(`${CONFIG.API_ENDPOINT}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                latitude: lat,
                longitude: lon,
                altitude: alt,
                time,
                chat_history: state.chatHistory.slice(0, -1),
            }),
        });

        if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
        }

        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        const isNdjsonStream = contentType.includes('application/x-ndjson');

        if (isNdjsonStream && response.body) {
            let streamedText = '';
            let receivedAnyContent = false;

            await streamNdjson(response, (chunk) => {
                if (chunk.type === 'error') {
                    throw new Error(chunk.error || 'Streaming failed');
                }

                if (chunk.type === 'response') {
                    const piece = chunk.content || '';
                    if (piece) {
                        receivedAnyContent = true;
                        streamedText += piece;
                        pendingAssistant.append(piece);
                    }
                }

                if (chunk.type === 'direct_response') {
                    const full = chunk.content || '';
                    receivedAnyContent = true;
                    streamedText = full;
                    pendingAssistant.setContent(full);
                }
            });

            pendingAssistant.finalize();

            if (receivedAnyContent && streamedText.trim()) {
                state.chatHistory.push({ role: 'assistant', content: streamedText.trim() });
            } else {
                pendingAssistant.setContent('No response');
                state.chatHistory.push({ role: 'assistant', content: 'No response' });
            }
        } else {
            // Direct non-streamed answer path.
            const data = await response.json();

            if (data.success) {
                const msg = data.response || 'No response';
                pendingAssistant.setContent(msg);
                pendingAssistant.finalize();
                state.chatHistory.push({ role: 'assistant', content: msg });
            } else {
                throw new Error(data.error || 'Failed to get response');
            }
        }
    } catch (error) {
        pendingAssistant.remove();
        addMessage(`Error: ${error.message}`, 'error');
        state.chatHistory.pop();
    } finally {
        elements.chatInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.chatInput.focus();
    }
}

function addMessage(content, role) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`;
    
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper';
    
    if (role === 'user') {
        const avatar = document.createElement('div');
        avatar.className = 'user-avatar';
        avatar.textContent = '👤';
        
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = content;
        
        wrapper.appendChild(avatar);
        wrapper.appendChild(bubble);
    } else if (role === 'assistant') {
        const avatar = document.createElement('div');
        avatar.className = 'ai-avatar';
        avatar.textContent = '🤖';
        
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';

        bubble.innerHTML = formatAssistantContent(content);
        
        wrapper.appendChild(avatar);
        wrapper.appendChild(bubble);
    } else {
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = content;
        wrapper.appendChild(bubble);
    }
    
    msgDiv.appendChild(wrapper);
    elements.chatContainer.appendChild(msgDiv);
    
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

function goBack() {
    hideChatLoading();
    elements.pageChat.classList.add('hidden');
    elements.pageLocation.classList.remove('hidden');
}

function showChatLoading(text) {
    updateLoadingText(text);
    if (!elements.chatContainer.contains(elements.chatLoading)) {
        elements.chatContainer.appendChild(elements.chatLoading);
    }
    elements.chatLoading.classList.remove('hidden');
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

function hideChatLoading() {
    elements.chatLoading.classList.add('hidden');
}

function formatAssistantContent(content) {
    return String(content)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function createStreamingAssistantMessage(showInlineLoader = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'chat-message assistant';

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper';

    const avatar = document.createElement('div');
    avatar.className = 'ai-avatar';
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    if (showInlineLoader) {
        bubble.innerHTML = `
            <div class="inline-thinking" aria-live="polite">
                <span class="inline-thinking-label">Thinking</span>
                <span class="inline-loader" aria-hidden="true">
                    <span class="inline-loader-bar"></span>
                    <span class="inline-loader-bar"></span>
                    <span class="inline-loader-bar"></span>
                    <span class="inline-loader-bar"></span>
                </span>
            </div>
        `;
    }

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    msgDiv.appendChild(wrapper);
    elements.chatContainer.appendChild(msgDiv);

    let accumulated = '';
    const append = (chunk) => {
        if (!chunk) return;
        accumulated += chunk;
        bubble.innerHTML = formatAssistantContent(accumulated);
        elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
    };

    const setContent = (content) => {
        accumulated = content || '';
        bubble.innerHTML = formatAssistantContent(accumulated);
        elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
    };

    const finalize = () => {
        bubble.innerHTML = formatAssistantContent(accumulated.trim());
        elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
    };

    const remove = () => {
        if (msgDiv.parentNode) {
            msgDiv.parentNode.removeChild(msgDiv);
        }
    };

    return { append, setContent, finalize, remove };
}

async function streamNdjson(response, onChunk) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            let chunk;
            try {
                chunk = JSON.parse(trimmed);
            } catch {
                // Ignore malformed partial lines.
                continue;
            }

            onChunk(chunk);
        }
    }

    const tail = buffer.trim();
    if (tail) {
        let chunk;
        try {
            chunk = JSON.parse(tail);
        } catch {
            // Ignore malformed trailing chunk.
            return;
        }

        onChunk(chunk);
    }
}

function getISOTime() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    
    const offset = new Date().getTimezoneOffset();
    const offsetHours = Math.floor(Math.abs(offset) / 60);
    const offsetMinutes = Math.abs(offset) % 60;
    const sign = offset > 0 ? '-' : '+';
    const tz = `${sign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;
    
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${tz}`;
}

function showStatus(msg, type) {
    elements.locationStatus.textContent = msg;
    elements.locationStatus.className = `status-message show ${type}`;
}

function updateLoadingText(text) {
    const loadingTitle = elements.chatLoading.querySelector('.loading-title');
    if (loadingTitle) {
        loadingTitle.textContent = text;
    }
}
