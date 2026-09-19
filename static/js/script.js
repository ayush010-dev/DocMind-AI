const API_URL = "";

let activeDocuments = [];
let currentChatId = null;
let chatHistory = [];

// =====================================================
// Elements
// =====================================================

const uploadPanel = document.getElementById("uploadPanel");
const welcomeScreen = document.getElementById("welcomeScreen");
const currentDocument = document.getElementById("currentDocument");

const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");

const newChatBtn = document.getElementById("newChatBtn");

const questionBox = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");

const chatBox = document.getElementById("chatBox");

const documentList = document.getElementById("documentList");

const chatHistoryContainer = document.getElementById("chatHistory");

// =====================================================
// Page Load
// =====================================================

document.addEventListener("DOMContentLoaded", () => {
  loadChats();
});

// =====================================================
// Load Chats from Database
// =====================================================

async function loadChats() {
  if (!chatHistoryContainer) {
    return;
  }

  try {
    const response = await fetch(`${API_URL}/chats`);

    if (!response.ok) {
      throw new Error("Failed to load chats.");
    }

    const chats = await response.json();

    chatHistoryContainer.innerHTML = "";

    if (!chats.length) {
      chatHistoryContainer.innerHTML = `
                <p class="empty-chats">
                    No conversations yet.
                </p>
            `;

      return;
    }

    chats.forEach((chat) => {
      createChatItem(chat);
    });
  } catch (error) {
    console.error("Chat history error:", error);
    if (chatHistoryContainer) {
        chatHistoryContainer.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
    }
  }
}

// =====================================================
// Create Sidebar Chat Item
// =====================================================

function createChatItem(chat) {
  const item = document.createElement("div");

  item.className = "chat-item";

  item.dataset.chatId = chat.id;

  const title = chat.title || "Untitled Chat";

  const time = formatChatTime(chat.created_at);

  item.innerHTML = `
        <div class="chat-title">
            <i class="fa-regular fa-message"></i>
            <span class="chat-title-text">${escapeHTML(title)}</span>
        </div>
        <div class="chat-time">
            ${time}
        </div>
    `;

  item.addEventListener("click", () => loadChat(chat.id));

  chatHistoryContainer.appendChild(item);
}

// =====================================================
// Load Selected Chat
// =====================================================

async function loadChat(chatId) {
  try {
    const response = await fetch(`${API_URL}/chats/${chatId}`);

    if (!response.ok) {
      throw new Error("Failed to load conversation.");
    }

    const data = await response.json();

    console.log("Loaded chat:", data);

    // ---------------------------------------------
    // Set Current Chat
    // ---------------------------------------------

    currentChatId = data.chat_id;

    // ---------------------------------------------
    // Set Document IDs and Render List
    // ---------------------------------------------

    activeDocuments = data.documents || [];
    renderDocumentList();

    // ---------------------------------------------
    // Clear Current Messages
    // ---------------------------------------------

    chatBox.querySelectorAll('.chat-message').forEach(m => m.remove());

    chatHistory = [];

    // ---------------------------------------------
    // Restore Messages
    // ---------------------------------------------

    data.messages.forEach((message) => {
      const type = message.role === "user" ? "user" : "ai";

      const sender = message.role === "user" ? "You" : "DocMind AI";

      addMessage(sender, message.content, type, message.document_sources || message.sources || [], message.web_sources || []);

      // Restore history
      chatHistory.push({
        role: message.role,

        content: message.content,
      });
    });

    // ---------------------------------------------
    // Update Active Sidebar Item
    // ---------------------------------------------

    document.querySelectorAll(".chat-item").forEach((item) => {
      item.classList.remove("active");
    });

    const selectedItem = document.querySelector(
      `.chat-item[data-chat-id="${chatId}"]`,
    );

    if (selectedItem) {
      selectedItem.classList.add("active");
    }

    // ---------------------------------------------
    // Show Chat Screen
    // ---------------------------------------------

    if (uploadPanel) {
      uploadPanel.classList.add("hidden");
    }

    if (welcomeScreen) {
      welcomeScreen.classList.add("hidden");
    }

    console.log("Current Chat ID:", currentChatId);
  } catch (error) {
    console.error("Load chat error:", error);
  }
}

// =====================================================
// Render Document List
// =====================================================

function renderDocumentList() {
    if (!documentList) return;
    
    documentList.innerHTML = "";
    
    if (activeDocuments.length === 0) {
        if (currentDocument) currentDocument.innerText = "No documents selected";
        return;
    }
    
    activeDocuments.forEach(doc => {
        const card = document.createElement("div");
        card.className = "header-doc-chip";
        card.title = doc.filename;
        
        let statusClass = "ready";
        if (doc.status === "processing") statusClass = "processing";
        else if (doc.status === "failed") statusClass = "failed";
        
        const currentStatus = doc.status || 'ready';
        const dashStyle = currentStatus !== 'ready' ? 'opacity: 0.5; pointer-events: none;' : '';

        card.innerHTML = `
            <div class="chip-status ${statusClass}" title="${escapeHTML(doc.error_message || doc.status || 'Ready')}"></div>
            <i class="fa-solid fa-file-lines chip-icon"></i>
            <div class="chip-name">${escapeHTML(doc.filename)}</div>
            <div class="chip-actions">
                <button class="chip-btn" title="Intelligence Dashboard" style="${dashStyle}" onclick="openIntelligenceDashboard('${doc.document_id}', '${escapeHTML(doc.filename)}')"><i class="fa-solid fa-brain"></i></button>
                <button class="chip-btn remove-btn" title="Remove Document" onclick="removeDocument('${doc.document_id}')"><i class="fa-solid fa-xmark"></i></button>
            </div>
        `;
        documentList.appendChild(card);
    });
    
    if (currentDocument) {
        currentDocument.innerText = activeDocuments.length > 1 ? `${activeDocuments.length} Documents` : activeDocuments[0].filename;
    }
}

// =====================================================
// Remove Document
// =====================================================

async function removeDocument(documentId) {
    if (!confirm("Are you sure you want to remove this document?")) return;
    
    try {
        const response = await fetch(`${API_URL}/documents/${documentId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error("Failed to delete document");
        }
        
        // Remove from active workspace
        activeDocuments = activeDocuments.filter(doc => doc.document_id !== documentId);
        renderDocumentList();
        
        // Reload sidebar chats UI
        await loadChats();
        
        // Let the user know
        if (currentChatId) {
            // Check if the current chat still exists (it was likely deleted)
            const chatExists = Array.from(document.querySelectorAll('.chat-item')).some(item => item.dataset.chatId === String(currentChatId));
            
            if (!chatExists) {
                // The chat was deleted, clear the screen
                currentChatId = null;
                chatBox.querySelectorAll('.chat-message').forEach(m => m.remove());
                if (welcomeScreen) welcomeScreen.classList.remove('hidden');
                if (uploadPanel) uploadPanel.classList.add('hidden');
            } else {
                addMessage("DocMind AI", "Document has been removed from this session.", "ai");
            }
        }
        
    } catch (error) {
        console.error("Delete document error:", error);
        alert("Failed to delete document.");
    }
}

// =====================================================
// New Chat
// =====================================================

function startNewChat() {
  chatHistory = [];

  activeDocuments = [];
  renderDocumentList();
  currentChatId = null;

  chatBox.querySelectorAll('.chat-message').forEach(m => m.remove());

  questionBox.value = "";

  addMessage(
    "DocMind AI",
    "New conversation started. Ask anything about your current document.",
    "ai",
  );

  // Remove active state

  document.querySelectorAll(".chat-item").forEach((item) => {
    item.classList.remove("active");
  });
}

if (newChatBtn) {
  newChatBtn.addEventListener("click", startNewChat);
}

// =====================================================
// Press Enter to Send
// =====================================================

if (questionBox) {
  questionBox.addEventListener("keypress", (e) => {
    const enterToSend = localStorage.getItem("enterToSend") !== "false";
    
    if (e.key === "Enter") {
      if (enterToSend && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
      }
    }
  });
}

// =====================================================
// Upload Elements & Listeners
// =====================================================
const browseBtn = document.getElementById("browseBtn");
const uploadBox = document.getElementById("uploadBox");
const uploadTitle = document.getElementById("uploadTitle");
const uploadError = document.getElementById("uploadError");

// Sidebar upload button
if (uploadBtn) {
  uploadBtn.addEventListener("click", () => {
    if (!isUploading && fileInput) fileInput.click();
  });
}
// Main area browse button
if (browseBtn) {
  browseBtn.addEventListener("click", () => {
    if (!isUploading && fileInput) fileInput.click();
  });
}
// Inline upload button
const inlineUploadBtn = document.getElementById("inlineUploadBtn");
if (inlineUploadBtn) {
  inlineUploadBtn.addEventListener("click", () => {
    if (!isUploading && fileInput) fileInput.click();
  });
}

// =====================================================
// Drag & Drop
// =====================================================
if (uploadBox) {
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadBox.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    uploadBox.addEventListener(eventName, highlight, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    uploadBox.addEventListener(eventName, unhighlight, false);
  });

  function highlight(e) {
    if (isUploading) return;
    uploadBox.style.borderColor = "var(--brand-main)";
    uploadBox.style.transform = "translateY(-4px)";
    if (uploadTitle) uploadTitle.innerText = "Drop your document here";
  }

  function unhighlight(e) {
    if (isUploading) return;
    uploadBox.style.borderColor = "";
    uploadBox.style.transform = "";
    if (uploadTitle) uploadTitle.innerText = "Upload your document";
  }

  uploadBox.addEventListener('drop', handleDrop, false);

  function handleDrop(e) {
    if (isUploading) return;
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) {
      handleUpload(files[0]);
    }
  }
}

if (fileInput) {
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      handleUpload(fileInput.files[0]);
    }
  });
}

// =====================================================
// Core Upload Function
// =====================================================
const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".xlsx"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB
let isUploading = false;

function showError(msg) {
  if (uploadError) {
    uploadError.innerText = msg;
    uploadError.classList.remove("hidden");
  }
}

function hideError() {
  if (uploadError) {
    uploadError.innerText = "";
    uploadError.classList.add("hidden");
  }
}

async function handleUpload(file) {
  if (isUploading) return;
  hideError();

  // Validate File
  if (!file) return;

  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    showError("Unsupported file type. Please upload PDF, DOCX, PPTX, TXT or XLSX.");
    if (fileInput) fileInput.value = "";
    return;
  }

  if (file.size > MAX_FILE_SIZE) {
    showError("File is too large. Maximum file size is 20 MB.");
    if (fileInput) fileInput.value = "";
    return;
  }

  // Upload State
  isUploading = true;
  if (browseBtn) browseBtn.disabled = true;
  if (uploadBtn) uploadBtn.disabled = true;
  if (uploadTitle) uploadTitle.innerText = "Uploading document...";
  if (uploadStatus) uploadStatus.innerText = "Uploading...";
  if (uploadBox) {
    uploadBox.style.borderColor = "";
    uploadBox.style.transform = "";
  }

  const formData = new FormData();
  formData.append("file", file);
  if (currentChatId) {
      formData.append("chat_id", currentChatId);
  }

  try {
    const response = await fetch(`${API_URL}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Upload failed.");
    }

    const data = await response.json();
    console.log("Upload response:", data);

    // Save IDs
    activeDocuments.push({
        document_id: data.document_id,
        filename: data.filename,
        status: data.status || "ready"
    });
    renderDocumentList();
    currentChatId = data.chat_id;
    
    if (!formData.has("chat_id")) {
      chatHistory = [];
    }

    // Success State
    if (uploadTitle) uploadTitle.innerText = "Document uploaded successfully";
    if (uploadStatus) uploadStatus.innerText = "";
    
    // Switch to chat view
    if (uploadPanel) uploadPanel.classList.add("hidden");
    if (welcomeScreen) welcomeScreen.classList.add("hidden");

    if (!formData.has("chat_id")) {
        chatBox.querySelectorAll('.chat-message').forEach(m => m.remove());
    }
    
    if (data.status === "processing") {
        addMessage(
          "DocMind AI",
          `Document "${data.filename}" is now processing in the background... You'll be notified when it's ready.`,
          "ai"
        );
        pollDocumentStatus(data.document_id);
    } else {
        openIntelligenceDashboard(data.document_id, data.filename);
        addMessage(
          "DocMind AI",
          `Document "${data.filename}" uploaded successfully.\n\nYou can now ask questions about it.`,
          "ai"
        );
    }

    // Refresh Sidebar Chats
    await loadChats();
    
    // Highlight Current Chat
    document.querySelectorAll(".chat-item").forEach((item) => {
      item.classList.remove("active");
    });
    const newChatItem = document.querySelector(`.chat-item[data-chat-id="${currentChatId}"]`);
    if (newChatItem) newChatItem.classList.add("active");

  } catch (error) {
    console.error("Upload error:", error);
    showError(error.message || "Upload Failed.");
    if (uploadStatus) uploadStatus.innerText = "Upload Failed.";
    if (uploadTitle) uploadTitle.innerText = "Upload your document";
  } finally {
    isUploading = false;
    if (browseBtn) browseBtn.disabled = false;
    if (uploadBtn) uploadBtn.disabled = false;
    if (fileInput) fileInput.value = "";
  }
}

// =====================================================
// Send Question
// =====================================================

if (sendBtn) {
  sendBtn.addEventListener("click", async () => {
    // -----------------------------------------
    // Check Document
    // -----------------------------------------

    if (activeDocuments.length === 0) {
      alert("Please upload at least one document first.");
      return;
    }

    // -----------------------------------------
    // Get Question
    // -----------------------------------------

    const question = questionBox.value.trim();
    const payload = {
      question: question,
      document_ids: activeDocuments.map(doc => doc.document_id),
      chat_id: currentChatId,
      chat_history: chatHistory,
    };

    if (!question) {
      return;
    }

    // -----------------------------------------
    // Show User Message
    // -----------------------------------------

    addMessage("You", question, "user");

    // -----------------------------------------
    // Clear Input
    // -----------------------------------------

    questionBox.value = "";

    // -----------------------------------------
    // Show Typing
    // -----------------------------------------

    showTyping();

    sendBtn.disabled = true;

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          question: question,
          document_ids: activeDocuments.map(doc => doc.document_id),
          chat_id: currentChatId,
          chat_history: chatHistory,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(errorData.detail || "Chat request failed.");
      }

      const data = await response.json();

      console.log("Chat response:", data);

      hideTyping();

      // -------------------------------------
      // Save Chat ID
      // -------------------------------------

      if (data.chat_id) {
        currentChatId = data.chat_id;
      }

      // -------------------------------------
      // AI Answer
      // -------------------------------------

      const answer = data.answer || "I couldn't generate an answer.";

      addMessage("DocMind AI", answer, "ai", data.document_sources || data.sources || [], data.web_sources || []);

      // -------------------------------------
      // Update Local History
      // -------------------------------------

      chatHistory.push({
        role: "user",

        content: question,
      });

      chatHistory.push({
        role: "assistant",

        content: answer,
      });

      // -------------------------------------
      // Refresh Sidebar
      // -------------------------------------

      await loadChats();

      // Highlight Current Chat

      const activeChat = document.querySelector(
        `.chat-item[data-chat-id="${currentChatId}"]`,
      );

      if (activeChat) {
        activeChat.classList.add("active");
      }
    } catch (error) {
      console.error("Chat error:", error);

      hideTyping();

      addMessage(
        "DocMind AI",
        `Something went wrong: ${error.message}`,
        "ai",
      );
    } finally {
      sendBtn.disabled = false;

      sendBtn.innerHTML = `
                    <i class="fa-solid fa-paper-plane"></i>
                `;
    }
  });
}

// =====================================================
// Add Message
// =====================================================

function addMessage(sender, message, type, sourcesParam = [], webSourcesParam = [], isHTML = false) {
  const wrapper = document.createElement("div");

  wrapper.className = `chat-message ${type}`;

  const safeMessage = String(message || "");

  let textContent = isHTML ? safeMessage : escapeHTML(safeMessage).replace(/\n/g, "<br>");

  let contentHtml = `
        <div class="avatar">
            ${
              type === "user"
                ? '<i class="fa-solid fa-user"></i>'
                : '<i class="fa-solid fa-robot"></i>'
            }
        </div>
        <div class="bubble">
            <div class="sender">
                ${escapeHTML(sender)}
            </div>
            <div class="text">
                ${textContent}
            </div>
  `;

  if (type === "ai") {
      let docList = [];
      let webList = [];

      // Extract document sources and web sources from parameters
      if (Array.isArray(sourcesParam)) {
          sourcesParam.forEach(src => {
              if (src && src.type === "web") {
                  webList.push(src);
              } else if (src && typeof src === "object") {
                  docList.push(src);
              }
          });
      } else if (sourcesParam && typeof sourcesParam === "object") {
          if (Array.isArray(sourcesParam.document_sources)) docList = sourcesParam.document_sources;
          if (Array.isArray(sourcesParam.web_sources)) webList = sourcesParam.web_sources;
      }

      if (Array.isArray(webSourcesParam) && webSourcesParam.length > 0) {
          webSourcesParam.forEach(w => {
              if (w && typeof w === "object") webList.push(w);
          });
      }

      // Deduplicate webList by URL and sanitize
      const uniqueWeb = [];
      const seenWeb = new Set();
      webList.forEach(w => {
          if (!w || !w.url || !w.title || String(w.url).includes("undefined") || String(w.title).includes("undefined")) return;
          const u = (w.url || "").trim();
          if (u && !seenWeb.has(u.toLowerCase())) {
              seenWeb.add(u.toLowerCase());
              uniqueWeb.push(w);
          }
      });
      webList = uniqueWeb;

      // Deduplicate docList by filename + page/slide/sheet/section and sanitize
      const uniqueDoc = [];
      const seenDoc = new Set();
      docList.forEach(d => {
          if (!d || (!d.filename && !d.source) || String(d.filename).includes("undefined") || String(d.label).includes("undefined")) return;
          const fn = d.filename || d.source || "Document";
          const key = `${d.document_id || ''}_${fn}_${d.page || ''}_${d.slide || ''}_${d.sheet || ''}_${d.section || ''}`;
          if (!seenDoc.has(key)) {
              seenDoc.add(key);
              uniqueDoc.push(d);
          }
      });
      docList = uniqueDoc;

      // Render Sources Section if at least one source exists
      if (docList.length > 0 || webList.length > 0) {
          contentHtml += `<hr class="source-divider" /><div class="sources-container"><div class="sources-header-main" style="font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 8px;">SOURCES</div>`;

          // Render Web Sources Section if available
          if (webList.length > 0) {
              contentHtml += `
                  <div class="sources-title"><i class="fa-solid fa-globe"></i> WEB SOURCES</div>
                  <div class="sources-list">
              `;
              webList.forEach(src => {
                  const title = src.title || src.domain || "Web Source";
                  const domainStr = src.domain ? ` · ${escapeHTML(src.domain)}` : '';
                  contentHtml += `
                      <div class="source-item web-source-item">
                          <div class="source-info">
                              <i class="fa-solid fa-globe"></i>
                              <span>${escapeHTML(title)}${domainStr}</span>
                          </div>
                          <a href="${escapeHTML(src.url)}" target="_blank" rel="noopener noreferrer" class="view-source-btn web-source-btn">
                              [ Open Source ]
                          </a>
                      </div>
                  `;
              });
              contentHtml += `</div>`;
          }

          // Render Document Sources Section if available
          if (docList.length > 0) {
              contentHtml += `
                  <div class="sources-title" style="${webList.length > 0 ? 'margin-top: 14px;' : ''}"><i class="fa-regular fa-file-lines"></i> DOCUMENT SOURCES</div>
                  <div class="sources-list">
              `;
              docList.forEach(src => {
                  let displayLabel = src.label;
                  if (!displayLabel) {
                      const docFileName = src.filename || src.source || "Document";
                      let details = [];
                      if (src.page) details.push(`Page ${src.page}`);
                      else if (src.slide) details.push(`Slide ${src.slide}`);
                      else if (src.sheet) details.push(`Sheet ${src.sheet}`);
                      else if (src.section) details.push(escapeHTML(src.section));
                      else if (src.chunk !== undefined) details.push(`Chunk ${src.chunk}`);
                      
                      const detailsStr = details.length > 0 ? ` · ${details.join(' · ')}` : '';
                      displayLabel = `${docFileName}${detailsStr}`;
                  }

                  let actionUrl = src.url;
                  if (!actionUrl) {
                      actionUrl = `/documents/${documentId}/source`;
                      if (src.page) actionUrl += `#page=${src.page}`;
                      else if (src.slide) actionUrl += `#slide=${src.slide}`;
                  }
                  
                  contentHtml += `
                      <div class="source-item doc-source-item">
                          <div class="source-info">
                              <i class="fa-regular fa-file"></i>
                              <span>${escapeHTML(displayLabel)}</span>
                          </div>
                          <a href="${actionUrl}" target="_blank" class="view-source-btn">
                              [ View Source ]
                          </a>
                      </div>
                  `;
              });
              contentHtml += `</div>`;
          }

          contentHtml += `</div>`;
      }
  }

  contentHtml += `</div>`;
  
  wrapper.innerHTML = contentHtml;

  chatBox.appendChild(wrapper);

  chatBox.scrollTop = chatBox.scrollHeight;
}

// =====================================================
// Typing Indicator
// =====================================================

function showTyping() {
  const showIndicator = localStorage.getItem("showTypingIndicator") !== "false";
  if (!showIndicator) return;

  if (document.getElementById("typingIndicator")) {
    return;
  }

  const typing = document.createElement("div");

  typing.className = "chat-message ai";

  typing.id = "typingIndicator";

  typing.innerHTML = `

        <div class="avatar">

            <i class="fa-solid fa-robot"></i>

        </div>


        <div class="bubble">

            <div class="sender">

                DocMind AI

            </div>


            <div class="typing">

                <span></span>

                <span></span>

                <span></span>

            </div>

        </div>

    `;

  chatBox.appendChild(typing);

  chatBox.scrollTop = chatBox.scrollHeight;
}

// =====================================================
// Hide Typing Indicator
// =====================================================

function hideTyping() {
  const typing = document.getElementById("typingIndicator");

  if (typing) {
    typing.remove();
  }
}

// =====================================================
// Format Chat Time
// =====================================================

function formatChatTime(timestamp) {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
  });
}

// =====================================================
// Escape HTML
// =====================================================

function escapeHTML(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// =====================================================
// Header Buttons & UI Logic
// =====================================================

// Elements
const searchBtn = document.getElementById("searchBtn");
const themeBtn = document.getElementById("themeBtn");
const settingsBtn = document.getElementById("settingsBtn");
const profileBtn = document.getElementById("profileBtn");

const searchPanel = document.getElementById("searchPanel");
const profileMenu = document.getElementById("profileMenu");
const settingsModal = document.getElementById("settingsModal");
const documentsModal = document.getElementById("documentsModal");
const intelligenceDashboard = document.getElementById("intelligenceDashboard");

const closeSearchBtn = document.getElementById("closeSearchBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const closeDocsBtn = document.getElementById("closeDocsBtn");

const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");

const myDocsBtn = document.getElementById("myDocsBtn");
const chatHistoryBtn = document.getElementById("chatHistoryBtn");
const openSettingsFromProfileBtn = document.getElementById("openSettingsFromProfileBtn");

const themeSelect = document.getElementById("themeSelect");
const enterToSendToggle = document.getElementById("enterToSendToggle");
const typingIndicatorToggle = document.getElementById("typingIndicatorToggle");
const themeIcon = document.getElementById("themeIcon");

// Global array of popups to easily close them all
const allPopups = [searchPanel, profileMenu, settingsModal, documentsModal, intelligenceDashboard];

function closeAllPopups() {
    allPopups.forEach(popup => {
        if (popup) popup.classList.add("hidden");
    });
}

function togglePopup(popup) {
    const isHidden = popup.classList.contains("hidden");
    closeAllPopups();
    if (isHidden) {
        popup.classList.remove("hidden");
        if (popup === searchPanel && searchInput) {
            searchInput.focus();
        }
    }
}

// Event Listeners for Header Buttons
if (searchBtn) searchBtn.addEventListener("click", (e) => { e.stopPropagation(); togglePopup(searchPanel); });
if (profileBtn) profileBtn.addEventListener("click", (e) => { e.stopPropagation(); togglePopup(profileMenu); });
if (settingsBtn) settingsBtn.addEventListener("click", (e) => { e.stopPropagation(); togglePopup(settingsModal); });
if (themeBtn) themeBtn.addEventListener("click", toggleTheme);

// Close Buttons
if (closeSearchBtn) closeSearchBtn.addEventListener("click", () => searchPanel.classList.add("hidden"));
if (closeSettingsBtn) closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));
if (closeDocsBtn) closeDocsBtn.addEventListener("click", () => documentsModal.classList.add("hidden"));

// Click outside to close
document.addEventListener("click", (e) => {
    // If clicking inside a popup, do nothing
    if (e.target.closest('.popup-panel') || e.target.closest('.modal-content') || e.target.closest('.icon-btn') || e.target.closest('.profile') || e.target.closest('.chip-btn')) {
        return;
    }
    closeAllPopups();
});

// Escape key to close
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeAllPopups();
    }
});

// Profile Menu Options
if (myDocsBtn) {
    myDocsBtn.addEventListener("click", () => {
        togglePopup(documentsModal);
        loadMyDocuments();
    });
}
if (chatHistoryBtn) {
    chatHistoryBtn.addEventListener("click", () => {
        closeAllPopups();
        // Focus sidebar
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) sidebar.scrollIntoView({behavior: "smooth"});
    });
}
if (openSettingsFromProfileBtn) {
    openSettingsFromProfileBtn.addEventListener("click", () => {
        togglePopup(settingsModal);
    });
}

// =====================================================
// Theme Logic
// =====================================================
function toggleTheme() {
    const isLight = document.body.classList.toggle("light-theme");
    const newTheme = isLight ? "light" : "dark";
    localStorage.setItem("theme", newTheme);
    updateThemeIcon(newTheme);
    if (themeSelect) themeSelect.value = newTheme;
}

function updateThemeIcon(theme) {
    if (!themeIcon) return;
    if (theme === "light") {
        themeIcon.className = "fa-solid fa-sun";
    } else {
        themeIcon.className = "fa-solid fa-moon";
    }
}

function loadTheme() {
    const savedTheme = localStorage.getItem("theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.add("light-theme");
    } else {
        document.body.classList.remove("light-theme");
    }
    updateThemeIcon(savedTheme);
    if (themeSelect) themeSelect.value = savedTheme;
}

// =====================================================
// Settings Logic
// =====================================================
function loadSettings() {
    const enterToSend = localStorage.getItem("enterToSend") !== "false";
    const showTyping = localStorage.getItem("showTypingIndicator") !== "false";
    
    if (enterToSendToggle) enterToSendToggle.checked = enterToSend;
    if (typingIndicatorToggle) typingIndicatorToggle.checked = showTyping;
}

if (themeSelect) {
    themeSelect.addEventListener("change", (e) => {
        const theme = e.target.value;
        if (theme === "light") {
            document.body.classList.add("light-theme");
        } else {
            document.body.classList.remove("light-theme");
        }
        localStorage.setItem("theme", theme);
        updateThemeIcon(theme);
    });
}

if (enterToSendToggle) {
    enterToSendToggle.addEventListener("change", (e) => {
        localStorage.setItem("enterToSend", e.target.checked);
    });
}

if (typingIndicatorToggle) {
    typingIndicatorToggle.addEventListener("change", (e) => {
        localStorage.setItem("showTypingIndicator", e.target.checked);
    });
}

// Initialize on load
loadTheme();
loadSettings();

// =====================================================
// Search Logic
// =====================================================
let searchTimeout;
if (searchInput) {
    searchInput.addEventListener("input", (e) => {
        clearTimeout(searchTimeout);
        const q = e.target.value.trim();
        if (!q) {
            searchResults.innerHTML = "";
            return;
        }
        
        searchTimeout = setTimeout(() => {
            performSearch(q);
        }, 300); // debounce
    });
}

async function performSearch(query) {
    try {
        searchResults.innerHTML = "<div class='search-result-item'>Searching...</div>";
        const response = await fetch(`${API_URL}/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error("Search failed");
        const results = await response.json();
        
        searchResults.innerHTML = "";
        if (results.length === 0) {
            searchResults.innerHTML = "<div class='search-result-item'>No results found</div>";
            return;
        }
        
        results.forEach(res => {
            const item = document.createElement("div");
            item.className = "search-result-item";
            item.innerHTML = `
                <div class="search-title">${escapeHTML(res.title || "Untitled")}</div>
                <div class="search-doc"><i class="fa-solid fa-file-lines"></i> ${escapeHTML(res.filename || "Unknown Doc")}</div>
            `;
            item.addEventListener("click", () => {
                closeAllPopups();
                searchInput.value = "";
                searchResults.innerHTML = "";
                loadChat(res.id);
            });
            searchResults.appendChild(item);
        });
    } catch (error) {
        console.error("Search error:", error);
        searchResults.innerHTML = "<div class='search-result-item'>Search error</div>";
    }
}

// =====================================================
// Documents Logic
// =====================================================
async function loadMyDocuments() {
    const docsList = document.getElementById("documentsList");
    if (!docsList) return;
    
    try {
        docsList.innerHTML = "<p>Loading documents...</p>";
        const response = await fetch(`${API_URL}/documents`);
        if (!response.ok) throw new Error("Failed to load documents");
        const docs = await response.json();
        
        docsList.innerHTML = "";
        if (docs.length === 0) {
            docsList.innerHTML = "<p>No documents uploaded yet.</p>";
            return;
        }
        
        docs.forEach(doc => {
            const item = document.createElement("div");
            item.className = "doc-item";
            const date = formatChatTime(doc.uploaded_at);
            item.innerHTML = `
                <div class="doc-item-title"><i class="fa-solid fa-file"></i> ${escapeHTML(doc.filename)}</div>
                <div class="doc-item-meta">Uploaded: ${date}</div>
            `;
            docsList.appendChild(item);
        });
    } catch (error) {
        console.error("Docs error:", error);
        docsList.innerHTML = "<p>Error loading documents.</p>";
    }
}

// =====================================================
// Intelligence Dashboard Logic
// =====================================================
const closeDashboardBtn = document.getElementById("closeDashboardBtn");
const dashFilename = document.getElementById("dashFilename");
const dashTopics = document.getElementById("dashTopics");
const examTabs = document.querySelectorAll(".exam-tabs .tab");
const generateExamBtn = document.getElementById("generateExamBtn");
const examDifficulty = document.getElementById("examDifficulty");
const examResults = document.getElementById("examResults");

let currentDashDocId = null;
let currentExamTab = "viva";

if (closeDashboardBtn) {
    closeDashboardBtn.addEventListener("click", () => {
        intelligenceDashboard.classList.add("hidden");
    });
}

function openIntelligenceDashboard(documentId, filename) {
    if (!documentId || documentId === 'undefined') {
        if (typeof activeDocuments !== 'undefined' && activeDocuments.length > 0) {
            documentId = activeDocuments[0].document_id;
            filename = activeDocuments[0].filename;
        } else {
            // Show notification toast if available, or just alert/add message
            if (typeof addMessage === 'function') {
                addMessage("DocMind AI", "Please upload or select a document first.", "ai");
            } else {
                alert("Please upload or select a document first.");
            }
            return;
        }
    }

    currentDashDocId = documentId;
    
    const dashFilename = document.getElementById("dashFilename");
    if (dashFilename) dashFilename.innerText = filename || 'Unknown';
    
    const dashTopics = document.getElementById("dashTopics");
    if (dashTopics) dashTopics.innerHTML = '<span class="chip loading">Extracting topics...</span>';
    
    const examResults = document.getElementById("examResults");
    if (examResults) examResults.innerHTML = '<div class="placeholder-text">Select an option and click Generate.</div>';
    
    // Show Modal
    closeAllPopups();
    if (intelligenceDashboard) intelligenceDashboard.classList.remove("hidden");
    
    // Fetch Topics
    fetchTopics(documentId);
}

async function fetchTopics(documentId) {
    try {
        const response = await fetch(`${API_URL}/intelligence/${documentId}/topics`);
        if (!response.ok) throw new Error("Failed to fetch topics");
        const data = await response.json();
        
        const topics = data.topics || [];
        if (topics.length === 0) {
            dashTopics.innerHTML = '<span class="chip">No topics found</span>';
            return;
        }
        
        dashTopics.innerHTML = "";
        topics.forEach(t => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.innerText = String(t);
            dashTopics.appendChild(chip);
        });
        
    } catch (error) {
        console.error("Topics error:", error);
        dashTopics.innerHTML = '<span class="chip loading" style="color:red">Failed to load</span>';
    }
}

// Exam Tabs Logic
examTabs.forEach(tab => {
    tab.addEventListener("click", (e) => {
        openExamTab(e.target.dataset.tab);
    });
});

function openExamTab(tabName) {
    currentExamTab = tabName;
    examTabs.forEach(t => t.classList.remove("active"));
    const activeTab = document.querySelector(`.exam-tabs .tab[data-tab="${tabName}"]`);
    if (activeTab) activeTab.classList.add("active");
    
    // Also scroll/focus to exam prep section if not visible
    generateExamBtn.scrollIntoView({behavior: "smooth", block: "center"});
}

if (generateExamBtn) {
    generateExamBtn.addEventListener("click", async () => {
        if (!currentDashDocId) return;
        
        const diff = examDifficulty.value;
        const type = currentExamTab;
        const count = document.getElementById("examCount") ? document.getElementById("examCount").value : 10;
        
        generateExamBtn.disabled = true;
        closeAllPopups();
        
        const promptLabel = `Generate ${count} ${type} questions (${diff} difficulty)`;
        addMessage("You", promptLabel, "user");
        showTyping();
        
        try {
            const response = await fetch(`${API_URL}/intelligence/${currentDashDocId}/exam?type=${type}&difficulty=${diff}&count=${count}`);
            if (!response.ok) throw new Error("Failed to generate exam prep");
            
            const data = await response.json();
            const questions = data.questions || [];
            
            hideTyping();
            if (questions.length === 0) {
                addMessage("DocMind AI", "Not enough information is available in the uploaded document to generate questions.", "ai");
                generateExamBtn.disabled = false;
                return;
            }
            
            let html = `<div style="display:flex; flex-direction:column; gap:15px;">`;
            let allSources = [];
            
            questions.forEach((q, index) => {
                html += `<div style="padding:10px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-secondary);">`;
                html += `<h5 style="margin-top:0;">Q${index + 1}. ${escapeHTML(q.question)}</h5>`;
                
                if (type === "mcq" && q.options) {
                    html += `<div style="display:flex; flex-direction:column; gap:5px; margin-top:8px;">`;
                    q.options.forEach(opt => {
                        const isCorrect = opt === q.correct_answer;
                        const bg = isCorrect ? "rgba(34,197,94,0.15)" : "var(--bg-tertiary)";
                        const border = isCorrect ? "1px solid #22c55e" : "1px solid var(--border-color)";
                        html += `<div style="padding:8px; border-radius:4px; background:${bg}; border:${border}; font-size:14px;">${escapeHTML(opt)}</div>`;
                    });
                    html += `</div>`;
                    if (q.explanation) {
                        html += `<p style="font-size:13px; color:var(--text-muted); margin-top:8px;"><strong>Explanation:</strong> ${escapeHTML(q.explanation)}</p>`;
                    }
                } else {
                    html += `<p style="font-size:14px; margin-top:8px;"><strong>Answer:</strong><br/>${escapeHTML(q.answer || "").replace(/\n/g, "<br>")}</p>`;
                }
                html += `</div>`;
                
                if (q.sources) allSources = allSources.concat(q.sources);
            });
            html += `</div>`;
            
            // Deduplicate sources
            const uniqueSources = [];
            const srcKeys = new Set();
            allSources.forEach(s => {
                const key = s.document_id + s.location;
                if (!srcKeys.has(key)) {
                    srcKeys.add(key);
                    uniqueSources.push(s);
                }
            });
            
            addMessage("DocMind AI", html, "ai", uniqueSources, [], true);
            
            chatHistory.push({ role: "user", content: promptLabel });
            chatHistory.push({ role: "assistant", content: `Generated ${questions.length} questions.` });
            
        } catch (error) {
            console.error("Exam generation error:", error);
            hideTyping();
            addMessage("DocMind AI", "Failed to generate questions. Please try again.", "ai");
        } finally {
            generateExamBtn.disabled = false;
        }
    });
}

// =====================================================
// Dashboard Quick Actions & Tools
// =====================================================

async function handleQuickAction(actionType) {
    if (activeDocuments.length === 0) {
        alert("Please select a document first.");
        return;
    }
    
    let promptLabel = "";
    let endpoint = "";
    
    // Exam routes that use GET /intelligence/{id}/exam
    if (['viva', '5mark', 'mcq'].includes(actionType)) {
        promptLabel = `Generate ${actionType} questions`;
        const docId = activeDocuments[0].document_id;
        
        closeAllPopups();
        addMessage("You", promptLabel, "user");
        showTyping();
        
        try {
            const response = await fetch(`${API_URL}/intelligence/${docId}/exam?type=${actionType}&difficulty=Medium&count=5`);
            if (!response.ok) throw new Error("Failed to generate exam prep");
            const data = await response.json();
            hideTyping();
            
            if (!data.questions || data.questions.length === 0) {
                addMessage("DocMind AI", "Not enough information is available in the uploaded document to generate questions.", "ai");
                return;
            }
            
            let html = `<div style="display:flex; flex-direction:column; gap:15px;">`;
            data.questions.forEach((q, index) => {
                html += `<div style="padding:10px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-secondary);">`;
                html += `<h5 style="margin-top:0;">Q${index + 1}. ${escapeHTML(q.question)}</h5>`;
                if (actionType === "mcq" && q.options) {
                    html += `<div style="display:flex; flex-direction:column; gap:5px; margin-top:8px;">`;
                    q.options.forEach(opt => {
                        const isCorrect = opt === q.correct_answer;
                        const bg = isCorrect ? "rgba(34,197,94,0.15)" : "var(--bg-tertiary)";
                        const border = isCorrect ? "1px solid #22c55e" : "1px solid var(--border-color)";
                        html += `<div style="padding:8px; border-radius:4px; background:${bg}; border:${border}; font-size:14px;">${escapeHTML(opt)}</div>`;
                    });
                    html += `</div>`;
                    if (q.explanation) {
                        html += `<p style="font-size:13px; color:var(--text-muted); margin-top:8px;"><strong>Explanation:</strong> ${escapeHTML(q.explanation)}</p>`;
                    }
                } else {
                    html += `<p style="font-size:14px; margin-top:8px;"><strong>Answer:</strong><br/>${escapeHTML(q.answer || "").replace(/\n/g, "<br>")}</p>`;
                }
                html += `</div>`;
            });
            html += `</div>`;
            
            addMessage("DocMind AI", html, "ai", [], [], true);
            chatHistory.push({ role: "user", content: promptLabel });
            chatHistory.push({ role: "assistant", content: `Generated ${data.questions.length} questions.` });
            
        } catch (error) {
            console.error(error);
            hideTyping();
            addMessage("DocMind AI", "Failed to generate questions. Please try again.", "ai");
        }
        return;
    }
    
    // Document Intelligence tools that use POST /intelligence/...
    if (actionType === 'summary') {
        promptLabel = "Generate a concise summary";
        endpoint = "/intelligence/summary";
    } else if (actionType === 'revision') {
        promptLabel = "Generate revision notes";
        endpoint = "/intelligence/revision";
    } else if (actionType === 'important') {
        promptLabel = "Generate important topics";
        endpoint = "/intelligence/important";
    } else if (actionType === 'flashcards') {
        promptLabel = "Generate flashcards";
        endpoint = "/intelligence/flashcards";
    } else return;
    
    closeAllPopups();
    addMessage("You", promptLabel, "user");
    showTyping();
    
    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                document_ids: activeDocuments.map(doc => doc.document_id)
            }),
        });

        if (!response.ok) throw new Error("Quick action request failed.");
        const data = await response.json();
        hideTyping();

        let aiResponse = "";

        if (actionType === 'summary') {
            aiResponse = data.summary || "Failed to generate summary.";
            addMessage("DocMind AI", aiResponse, "ai");
        } else if (actionType === 'flashcards') {
            const cards = data.flashcards || [];
            if (cards.length > 0) {
                renderFlashcardsJSON(cards);
                aiResponse = `Generated ${cards.length} flashcards.`;
            } else {
                aiResponse = "Failed to generate flashcards.";
                addMessage("DocMind AI", aiResponse, "ai");
            }
        } else if (actionType === 'revision') {
            if (data.revision_notes) {
                const rn = data.revision_notes;
                let html = `<h4>${escapeHTML(rn.topic || "Revision Notes")}</h4>`;
                if (rn.key_concepts && rn.key_concepts.length) {
                    html += `<h5>Key Concepts</h5><ul>${rn.key_concepts.map(c => `<li>${escapeHTML(c)}</li>`).join('')}</ul>`;
                }
                if (rn.important_definitions && rn.important_definitions.length) {
                    html += `<h5>Important Definitions</h5><ul>${rn.important_definitions.map(c => `<li>${escapeHTML(c)}</li>`).join('')}</ul>`;
                }
                if (rn.important_facts && rn.important_facts.length) {
                    html += `<h5>Important Facts</h5><ul>${rn.important_facts.map(c => `<li>${escapeHTML(c)}</li>`).join('')}</ul>`;
                }
                if (rn.things_to_remember && rn.things_to_remember.length) {
                    html += `<h5>Things to Remember</h5><ul>${rn.things_to_remember.map(c => `<li>${escapeHTML(c)}</li>`).join('')}</ul>`;
                }
                addMessage("DocMind AI", html, "ai", [], [], true);
                aiResponse = "Generated revision notes.";
            } else {
                aiResponse = "Failed to generate revision notes.";
                addMessage("DocMind AI", aiResponse, "ai");
            }
        } else if (actionType === 'important') {
            const topics = data.important_topics || [];
            if (topics.length > 0) {
                let html = `<div style="display:flex; flex-direction:column; gap:10px;">`;
                topics.forEach(t => {
                    html += `<div style="padding:10px; background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:6px;">
                        <h5 style="margin:0 0 5px 0;">${escapeHTML(t.topic)}</h5>
                        <p style="margin:0; font-size:13px; color:var(--text-muted);">${escapeHTML(t.why_important)}</p>
                    </div>`;
                });
                html += `</div>`;
                addMessage("DocMind AI", html, "ai", [], [], true);
                aiResponse = "Generated important topics.";
            } else {
                aiResponse = "Failed to generate important topics.";
                addMessage("DocMind AI", aiResponse, "ai");
            }
        }

        chatHistory.push({ role: "user", content: promptLabel });
        chatHistory.push({ role: "assistant", content: aiResponse });
        
    } catch (error) {
        console.error("Quick Action error:", error);
        hideTyping();
        addMessage("DocMind AI", `Error: ${error.message}`, "ai");
    }
}

function renderFlashcardsJSON(cards) {
    if (!cards || cards.length === 0) {
        addMessage("DocMind AI", "No flashcards generated.", "ai");
        return;
    }
    
    // Generate interactive UI
    const containerId = "flashcards-" + Date.now();
    let html = `<div id="${containerId}" class="flashcard-container" style="position:relative; width:100%; max-width:400px; height:250px; margin: 15px 0; perspective:1000px; display:flex; flex-direction:column; gap:10px;">`;
    
    cards.forEach((c, idx) => {
        const display = idx === 0 ? "block" : "none";
        html += `
            <div class="fc-wrapper" data-index="${idx}" style="display:${display}; flex:1; position:relative; cursor:pointer; transform-style:preserve-3d; transition:transform 0.6s;" onclick="this.style.transform = this.style.transform === 'rotateY(180deg)' ? 'rotateY(0deg)' : 'rotateY(180deg)'">
                <div class="fc-front" style="position:absolute; width:100%; height:100%; backface-visibility:hidden; background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:12px; display:flex; align-items:center; justify-content:center; padding:20px; text-align:center; font-weight:bold; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                    ${escapeHTML(c.front).replace(/\\n/g, "<br>")}
                    <div style="position:absolute; bottom:10px; font-size:11px; color:var(--text-muted);">Click to flip</div>
                </div>
                <div class="fc-back" style="position:absolute; width:100%; height:100%; backface-visibility:hidden; background:var(--primary-color); color:white; border-radius:12px; display:flex; align-items:center; justify-content:center; padding:20px; text-align:center; transform:rotateY(180deg); box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow-y:auto;">
                    ${escapeHTML(c.back).replace(/\\n/g, "<br>")}
                </div>
            </div>
        `;
    });
    
    html += `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
            <button onclick="changeFlashcard('${containerId}', -1, ${cards.length})" class="icon-btn" style="background:var(--bg-tertiary); padding:5px 15px; border-radius:4px;"><i class="fa-solid fa-arrow-left"></i> Prev</button>
            <span id="${containerId}-counter" style="font-size:13px; color:var(--text-muted);">1 / ${cards.length}</span>
            <button onclick="changeFlashcard('${containerId}', 1, ${cards.length})" class="icon-btn" style="background:var(--bg-tertiary); padding:5px 15px; border-radius:4px;">Next <i class="fa-solid fa-arrow-right"></i></button>
        </div>
    </div>`;
    
    addMessage("DocMind AI", html, "ai", sources?.document_sources, sources?.web_sources, true);
}

window.changeFlashcard = function(containerId, dir, total) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const cards = container.querySelectorAll('.fc-wrapper');
    let currentIndex = 0;
    cards.forEach((c, idx) => {
        if (c.style.display === "block") currentIndex = idx;
    });
    
    cards[currentIndex].style.display = "none";
    cards[currentIndex].style.transform = "rotateY(0deg)"; // reset flip
    
    let nextIndex = currentIndex + dir;
    if (nextIndex < 0) nextIndex = total - 1;
    if (nextIndex >= total) nextIndex = 0;
    
    cards[nextIndex].style.display = "block";
    document.getElementById(`${containerId}-counter`).innerText = `${nextIndex + 1} / ${total}`;
}

// =====================================================
// Find in Document
// =====================================================

function toggleFindInDocument() {
    if (activeDocuments.length === 0) {
        alert("Please select a document first.");
        return;
    }
    const container = document.getElementById("findInDocumentContainer");
    if (container) {
        if (container.classList.contains("hidden")) {
            container.classList.remove("hidden");
            document.getElementById("findInDocumentInput").focus();
        } else {
            container.classList.add("hidden");
        }
    }
}

async function executeFindInDocument() {
    if (activeDocuments.length === 0) return;
    const input = document.getElementById("findInDocumentInput").value.trim();
    const resultsContainer = document.getElementById("findInDocumentResults");
    
    if (!input) return;
    
    resultsContainer.innerHTML = '<div style="font-size:13px; color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Searching...</div>';
    
    try {
        const response = await fetch(`${API_URL}/intelligence/${activeDocuments[0].document_id}/search?q=${encodeURIComponent(input)}`);
        if (!response.ok) throw new Error("Search failed");
        
        const data = await response.json();
        const matches = data.matches || [];
        
        if (matches.length === 0) {
            resultsContainer.innerHTML = '<div style="font-size:13px; color:var(--text-muted);">No matches found.</div>';
            return;
        }
        
        let html = '<div style="display:flex; flex-direction:column; gap:10px;">';
        matches.forEach(m => {
            const pageInfo = (m.metadata && m.metadata.page) ? `Page ${m.metadata.page}` : (m.metadata && m.metadata.slide) ? `Slide ${m.metadata.slide}` : "Location unknown";
            const filename = (m.metadata && m.metadata.filename) ? m.metadata.filename : activeDocuments[0].filename;
            
            // Highlight the searched text
            const regex = new RegExp(`(${input.replace(/[-\/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&')})`, 'gi');
            const highlightedText = escapeHTML(m.text).replace(regex, '<mark style="background:var(--primary-color); color:white; padding:0 2px; border-radius:2px;">$1</mark>');
            
            html += `
                <div style="padding:10px; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-primary); font-size:13px;">
                    <div style="font-weight:bold; margin-bottom:5px; color:var(--primary-color);">
                        <i class="fa-regular fa-file"></i> ${escapeHTML(filename)} <span style="color:var(--text-muted); font-size:11px; margin-left:8px;">${pageInfo}</span>
                    </div>
                    <div style="color:var(--text-primary); line-height:1.5;">...${highlightedText}...</div>
                </div>
            `;
        });
        html += '</div>';
        
        resultsContainer.innerHTML = html;
        
    } catch (error) {
        console.error("Find error:", error);
        resultsContainer.innerHTML = '<div style="font-size:13px; color:red;">Search failed.</div>';
    }
}


// =====================================================
// Document Polling
// =====================================================

const documentPollers = {};

function pollDocumentStatus(documentId) {
    if (documentPollers[documentId]) return;
    
    documentPollers[documentId] = setInterval(async () => {
        try {
            const response = await fetch(`${API_URL}/documents/${documentId}/status`);
            if (response.ok) {
                const data = await response.json();
                const docRef = activeDocuments.find(d => d.document_id === documentId);
                
                if (docRef) {
                    docRef.status = data.status;
                    docRef.error_message = data.error_message;
                    renderDocumentList();
                    
                    if (data.status !== "processing") {
                        clearInterval(documentPollers[documentId]);
                        delete documentPollers[documentId];
                        
                        if (data.status === "ready") {
                            addMessage("DocMind AI", `Processing complete for document "${docRef.filename}". You can now chat!`, "ai");
                        } else if (data.status === "failed") {
                            addMessage("DocMind AI", `Failed to process document "${docRef.filename}": ${data.error_message}`, "ai");
                        }
                    }
                } else {
                    // Document removed from active view
                    clearInterval(documentPollers[documentId]);
                    delete documentPollers[documentId];
                }
            }
        } catch (error) {
            console.error("Polling error", error);
        }
    }, 2500);
}
