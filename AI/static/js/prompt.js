// Message sending functionality - Updated and Debugged
document.addEventListener('DOMContentLoaded', function() {
    const promptForm = document.getElementById('prompt-form');
    const promptInput = document.getElementById('prompt-input');
    const chatContainer = document.getElementById('chat-container');
    const introSection = document.querySelector('.intro');
    const promptBar = document.querySelector('.prompt');
    const sendBtn = document.getElementById('send-btn');
    
    let isAIResponding = false;
    let typingInterval = null;
    let currentChatId = null;
    
    console.log('Chat container loaded');
    
    // Load chat history when page loads
    loadChatHistory();
    
    // Check for chat ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const chatIdFromUrl = urlParams.get('chat');
    if (chatIdFromUrl) {
        currentChatId = chatIdFromUrl;
        loadChat(chatIdFromUrl);
    }
    
    // Auto-adjust textarea height
    promptInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        
        if (this.scrollHeight > 200) {
            this.style.overflowY = 'auto';
        } else {
            this.style.overflowY = 'hidden';
        }
    });
    
    // Enter and Shift+Enter key control
    promptInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (!e.shiftKey) {
                e.preventDefault();
                if (!isAIResponding) {
                    promptForm.dispatchEvent(new Event('submit'));
                }
            }
        }
    });
    
    // Form submission
    promptForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const message = promptInput.value.trim();
        
        if (message && !isAIResponding) {
            console.log('Sending message:', message);
            
            // Start new chat if it's the first message
            if (!currentChatId) {
                console.log('Starting new chat...');
                const chatResult = await startNewChat();
                if (chatResult.success) {
                    currentChatId = chatResult.chat_id;
                    window.history.replaceState({}, '', `/?chat=${currentChatId}`);
                    console.log('New chat started with ID:', currentChatId);
                } else {
                    console.error('Chat start failed:', chatResult.error);
                    alert('Chat could not be started: ' + chatResult.error);
                    return;
                }
            }
            
            if (introSection && !introSection.classList.contains('active')) {
                introSection.classList.add('active');
                promptBar.classList.add('active');
                document.querySelector('.demo').classList.add('active');
            }
            
            // Display message on screen
            addMessage(message, 'user');
            
            // Save message to backend
            await saveMessageToBackend(currentChatId, 'user', message);
            
            promptInput.value = '';
            promptInput.style.height = 'auto';
            
            disableInput();
            showThinkingAnimation();

            // Get AI response
            const aiResponse = await generateAIResponse(message);

            removeThinkingAnimation();
            
            // Show response with typing effect (not adding directly)
            addMessageWithTypingEffect(aiResponse, 'ai');

            // Save AI message to backend
            await saveMessageToBackend(currentChatId, 'ai', aiResponse);

            // Refresh chat history
            loadChatHistory();
        }
    });
    
    // Load chat history from backend
    async function loadChatHistory() {
        try {
            console.log('Loading chat history...');
            const response = await fetch('/api/get_chats');
            const result = await response.json();
            console.log('Chat history result:', result);
            
            if (result.success) {
                renderChatHistory(result.chats);
            } else {
                console.error('Failed to load chat history:', result.error);
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }
    
    // Render chat history to sidebar
    function renderChatHistory(chats) {
        const chatList = document.querySelector('.nav-list.primary-nav');
        
        // Clear old chat items
        const chatItems = chatList.querySelectorAll('.chat-item');
        chatItems.forEach(item => item.remove());
        
        // Add new chat items
        chats.forEach(chat => {
            const listItem = document.createElement('li');
            listItem.classList.add('nav-item', 'chat-item');
            
            const link = document.createElement('a');
            link.href = `/?chat=${chat.id}`;
            link.classList.add('nav-link');
            link.onclick = (e) => {
                e.preventDefault();
                loadChat(chat.id);
            };
            
            const iconSpan = document.createElement('span');
            iconSpan.classList.add('material-symbols-rounded');
            iconSpan.textContent = 'forum';
            
            const labelSpan = document.createElement('span');
            labelSpan.classList.add('nav-label');
            labelSpan.textContent = chat.title;
            
            link.appendChild(iconSpan);
            link.appendChild(labelSpan);
            listItem.appendChild(link);
            
            // Add after existing "Chats" title
            const sidebarTitle = chatList.querySelector('.sidebar-title');
            if (sidebarTitle) {
                sidebarTitle.parentNode.insertBefore(listItem, sidebarTitle.nextSibling);
            } else {
                chatList.appendChild(listItem);
            }
        });
    }
    
    // Start new chat
    async function startNewChat() {
        try {
            console.log('Requesting new chat from server...');
            const response = await fetch('/api/start_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include' // Send session information
            });
            return await response.json();
        } catch (error) {
            console.error('Error starting chat:', error);
            return { success: false, error: error.message };
        }
    }
    
    // Save message to backend
    async function saveMessageToBackend(chatId, role, content) {
        try {
            console.log('Saving message to backend:', { chatId, role, content });
            
            const response = await fetch('/api/save_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'include',
                body: JSON.stringify({
                    chat_id: chatId,
                    role: role,
                    content: content
                })
            });
            
            // Check response headers
            console.log('Response status:', response.status, response.statusText);
            
            const result = await response.json();
            console.log('Save message response:', result);
            
            if (!result.success) {
                console.error('Message save failed:', result.error);
            }
            
            return result;
        } catch (error) {
            console.error('Error saving message:', error);
            return { success: false, error: error.message };
        }
    }
    
    // Load specific chat
    async function loadChat(chatId) {
        try {
            console.log('Loading chat:', chatId);
            const response = await fetch(`/api/get_messages/${chatId}`, {
                credentials: 'include',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            console.log('Load chat response status:', response.status);
            
            const result = await response.json();
            console.log('Load chat response:', result);
            
            if (result.success) {
                // Clear chat
                chatContainer.innerHTML = '';
                
                console.log('Messages to display:', result.messages.length);
                
                // Load messages
                result.messages.forEach(message => {
                    addMessage(message.content, message.role);
                });
                
                currentChatId = chatId;
                window.history.replaceState({}, '', `/?chat=${chatId}`);
                
                // Update UI
                if (introSection && !introSection.classList.contains('active')) {
                    introSection.classList.add('active');
                    promptBar.classList.add('active');
                    document.querySelector('.demo').classList.add('active');
                }
                
                scrollToBottom();
            } else {
                console.error('Failed to load chat:', result.error);
                alert('Chat could not be loaded: ' + result.error);
            }
        } catch (error) {
            console.error('Error loading chat:', error);
            alert('An error occurred while loading chat: ' + error.message);
        }
    }
    
    function disableInput() {
        isAIResponding = true;
        promptInput.disabled = true;
        promptInput.placeholder = "AI is responding...";
        sendBtn.disabled = true;
        sendBtn.style.opacity = "0.5";
        sendBtn.style.cursor = "not-allowed";
    }
    
    function enableInput() {
        isAIResponding = false;
        promptInput.disabled = false;
        promptInput.placeholder = "Ask anything";
        promptInput.focus();
        sendBtn.disabled = false;
        sendBtn.style.opacity = "1";
        sendBtn.style.cursor = "pointer";
    }
    
    // Update thinking animation function
    function showThinkingAnimation() {
        const thinkingDiv = document.createElement('div');
        thinkingDiv.classList.add('message', 'thinking-message');
        thinkingDiv.id = 'thinking-animation';
        
        addAILogo(thinkingDiv); // Add logo to thinking animation too
        
        const dotsDiv = document.createElement('div');
        dotsDiv.classList.add('thinking-dots');
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.classList.add('dot');
            dotsDiv.appendChild(dot);
        }
        
        thinkingDiv.appendChild(dotsDiv);
        chatContainer.appendChild(thinkingDiv);
        
        scrollToBottom();
    }
    
    function removeThinkingAnimation() {
        const thinkingElement = document.getElementById('thinking-animation');
        if (thinkingElement) {
            thinkingElement.remove();
        }
    }

    // Update logo adding function
    function addAILogo(element) {
        const aiLogo = document.createElement('div');
        aiLogo.classList.add('message-logo', 'ai-logo');
        
        // Hide IA text
        const textSpan = document.createElement('span');
        textSpan.classList.add('ai-logo-text');
        textSpan.innerHTML = '';
        textSpan.style.display = 'none'; // Completely hide text
        
        // Add logo image
        const logoImage = document.createElement('img');
        logoImage.classList.add('ai-logo-image');
        logoImage.src = "{{ url_for('static', filename='movie/Transparentlogo.png') }}";
        logoImage.alt = "Infini AI";
        logoImage.onerror = function() {
            // If logo fails to load, show IA text
            this.style.display = 'none';
            textSpan.style.display = 'block';
        };
        
        aiLogo.appendChild(textSpan);
        aiLogo.appendChild(logoImage);
        element.appendChild(aiLogo);
    }

    // Markdown to HTML conversion and sanitization function
    function formatMarkdown(content) {
        // Convert markdown to HTML
        const convertedHtml = marked.parse(content);
        
        // Sanitize HTML for security
        const cleanHtml = DOMPurify.sanitize(convertedHtml);
        
        return cleanHtml;
    }
    
    // Update message adding functions
    function addMessageWithTypingEffect(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender + '-message');
        messageDiv.id = 'typing-message';
        
        if (sender === 'ai') {
            addAILogo(messageDiv);
        }
        
        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.id = 'typing-text';
        messageDiv.appendChild(messageContent);
        
        const timeSpan = document.createElement('div');
        timeSpan.classList.add('message-time');
        timeSpan.id = 'typing-time';
        timeSpan.style.visibility = 'hidden';
        timeSpan.textContent = getCurrentTime();
        messageDiv.appendChild(timeSpan);
        
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
        
        startTypingEffect(text, messageContent, timeSpan);
    }
    
    function startTypingEffect(text, element, timeElement) {
        let index = 0;
        const typingSpeed = 30;

        function type() {
            if (index < text.length) {
                const partialText = text.substring(0, index + 1);

                // Parse Markdown even while typing
                const dirty = marked.parse(partialText);
                const clean = DOMPurify.sanitize(dirty);
                element.innerHTML = clean;

                index++;
                typingInterval = setTimeout(type, typingSpeed);
                scrollToBottom();
            } else {
                timeElement.style.visibility = 'visible';
                element.parentElement.parentElement.removeAttribute('id');
                enableInput();
                clearTimeout(typingInterval);
            }
        }

        type();
    }
    
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender + '-message');
        
        if (sender === 'ai') {
            addAILogo(messageDiv);
        }
        
        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        
        // Format markdown for AI messages
        if (sender === 'ai') {
            messageContent.innerHTML = formatMarkdown(text);
        } else {
            messageContent.textContent = text;
        }
        
        messageDiv.appendChild(messageContent);
        
        const timeSpan = document.createElement('div');
        timeSpan.classList.add('message-time');
        timeSpan.textContent = getCurrentTime();
        messageDiv.appendChild(timeSpan);
        
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
    }
    
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    function getCurrentTime() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' + 
               now.getMinutes().toString().padStart(2, '0');
    }
    
    // Get AI response
    async function generateAIResponse(userMessage) {
        try {
            console.log("Sending message to AI:", userMessage);
            
            // Get uploaded file information
            let fileContext = "";
            const fileItems = document.querySelectorAll('.file-item');
            if (fileItems.length > 0) {
                const fileNames = Array.from(fileItems).map(item => 
                    item.querySelector('.file-name').textContent);
                fileContext = ` User uploaded these files: ${fileNames.join(', ')}.`;
            }
            
            const response = await fetch("/api/ask_ai", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                credentials: "include",
                body: JSON.stringify({
                    chat_id: currentChatId,
                    message: userMessage + fileContext
                })
            });

            const result = await response.json();
            console.log("AI response:", result);

            if (result.success) {
                return result.response;
            } else {
                console.error("AI request failed:", result.error);
                return "An error occurred: " + result.error;
            }
        } catch (err) {
            console.error("Error getting AI response:", err);
            return "An error occurred: " + err.message;
        }
    }
    
   // Voice input feature
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {
        let recognition;
        let isRecording = false;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();

            recognition.continuous = false; // For single sentence recording
            recognition.interimResults = true; // Show real-time text while user speaks
            recognition.lang = "tr-TR"; // For Turkish
        } else {
            console.warn("Browser does not support voice input feature!");
            micBtn.addEventListener("click", () => {
                alert("Your browser does not support voice input.");
            });
            return;
        }

        micBtn.addEventListener("click", function() {
            if (isAIResponding) return; // Disabled if AI is responding

            if (!isRecording) {
                recognition.start();
                isRecording = true;
                micBtn.classList.add("recording"); // For animation/color on button
                promptInput.placeholder = "Listening... start speaking 🎤";
            } else {
                recognition.stop();
                isRecording = false;
                micBtn.classList.remove("recording");
                promptInput.placeholder = "Type your message...";
            }
        });

        recognition.onresult = function(event) {
            let transcript = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            promptInput.value = transcript; // Auto-write to text field
            promptInput.style.height = "auto"; // Update textarea height
            promptInput.style.height = (promptInput.scrollHeight) + "px";
        };

        recognition.onerror = function(event) {
            console.error("Speech recognition error:", event.error);
            isRecording = false;
            micBtn.classList.remove("recording");
            promptInput.placeholder = "Type your message...";
        };

        recognition.onend = function() {
            isRecording = false;
            micBtn.classList.remove("recording");
            promptInput.placeholder = "Type your message...";
        };
    }
    
    // Load markdown libraries
    const markedScript = document.createElement('script');
    markedScript.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
    document.head.appendChild(markedScript);
    
    const domPurifyScript = document.createElement('script');
    domPurifyScript.src = 'https://cdn.jsdelivr.net/npm/dompurify@2.3.3/dist/purify.min.js';
    document.head.appendChild(domPurifyScript);
});