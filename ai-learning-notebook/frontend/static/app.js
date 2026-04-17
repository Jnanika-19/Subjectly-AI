const CHAT_HISTORY_KEY = "subjectly-chat-history";

const state = {
  subjects: [],
  selectedSubjectId: null,
  notes: [],
  documents: [],
  mode: "study",
  chatHistory: [],
  quiz: [],
  toastTimer: null,
};

const subjectsList = document.getElementById("subjectsList");
const documentsList = document.getElementById("documentsList");
const notesContainer = document.getElementById("notesContainer");
const selectedSubjectLabel = document.getElementById("selectedSubjectLabel");
const chatThread = document.getElementById("chatThread");
const thinkingState = document.getElementById("thinkingState");
const questionInput = document.getElementById("questionInput");
const activeModeLabel = document.getElementById("activeModeLabel");
const toast = document.getElementById("toast");
const subjectsCount = document.getElementById("subjectsCount");
const notesCount = document.getElementById("notesCount");
const documentsCount = document.getElementById("documentsCount");
const modeMetric = document.getElementById("modeMetric");
const askBtn = document.getElementById("askBtn");
const selectedSubjectFiles = document.getElementById("selectedSubjectFiles");
const selectedSubjectNotes = document.getElementById("selectedSubjectNotes");
const chatMessagesCount = document.getElementById("chatMessagesCount");
const quizContainer = document.getElementById("quizContainer");

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(error.error || error.detail || "Request failed.");
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatModeLabel(mode) {
  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

function buildQuestionPayload(rawQuestion) {
  return {
    question: `[Mode: ${formatModeLabel(state.mode)}]\n${rawQuestion.trim()}`,
  };
}

function normalizeMarkdown(text) {
  if (!window.marked) {
    return `<p>${escapeHtml(text)}</p>`;
  }
  return marked.parse(text, { breaks: true, gfm: true });
}

function saveChatHistory() {
  localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(state.chatHistory));
}

function loadChatHistory() {
  try {
    state.chatHistory = JSON.parse(localStorage.getItem(CHAT_HISTORY_KEY) || "[]");
  } catch {
    state.chatHistory = [];
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 3200);
}

function setThinking(isThinking) {
  thinkingState.hidden = !isThinking;
  askBtn.disabled = isThinking;
}

function scrollChatToBottom() {
  chatThread.scrollTop = chatThread.scrollHeight;
}

function renderMessage(message) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${message.role}`;
  wrapper.innerHTML = `
    <div class="avatar">${message.role === "user" ? "YOU" : "AI"}</div>
    <div class="bubble markdown-body">${message.role === "assistant" ? normalizeMarkdown(message.content) : `<p>${escapeHtml(message.content)}</p>`}</div>
  `;
  chatThread.appendChild(wrapper);
}

function renderChatHistory() {
  chatThread.innerHTML = `
    <div class="message assistant">
      <div class="avatar">AI</div>
      <div class="bubble markdown-body">
        <p><strong>Welcome to Subjectly.</strong></p>
        <p>Upload notes, organize by subject, and chat with your own study material in a cleaner AI workspace.</p>
      </div>
    </div>
  `;
  state.chatHistory.forEach(renderMessage);
  updateMetrics();
  scrollChatToBottom();
}

function updateMetrics() {
  subjectsCount.textContent = String(state.subjects.length);
  notesCount.textContent = String(state.notes.length);
  documentsCount.textContent = String(state.documents.length);
  modeMetric.textContent = formatModeLabel(state.mode);
  selectedSubjectFiles.textContent = String(state.documents.length);
  selectedSubjectNotes.textContent = String(state.notes.length);
  chatMessagesCount.textContent = String(state.chatHistory.length);
}

function updateSelectedSubjectLabel() {
  const subject = state.subjects.find((item) => item.id === state.selectedSubjectId);
  selectedSubjectLabel.textContent = subject ? subject.name : "No subject selected";
}

function renderSubjects() {
  subjectsList.innerHTML = "";
  if (!state.subjects.length) {
    subjectsList.innerHTML = `
      <div class="empty-illustration">
        <div class="empty-orb"></div>
        <div>
          <strong>No subjects yet</strong>
          <p class="muted small">Create your first subject to start building your study dashboard.</p>
        </div>
      </div>
    `;
    return;
  }

  state.subjects.forEach((subject) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `subject-item ripple-btn ${state.selectedSubjectId === subject.id ? "active" : ""}`;
    item.innerHTML = `
      <div class="subject-title">${escapeHtml(subject.name)}</div>
      <div class="muted small">${escapeHtml(subject.description || "No description yet.")}</div>
      <div class="subject-meta">
        <span class="meta-pill">${subject.document_count || 0} files</span>
        <span class="meta-pill">${subject.note_count || 0} notes</span>
      </div>
    `;
    item.addEventListener("click", () => selectSubject(subject.id));
    subjectsList.appendChild(item);
  });
}

function renderDocuments() {
  documentsList.innerHTML = "";
  if (!state.documents.length) {
    documentsList.innerHTML = `
      <div class="empty-illustration">
        <div class="empty-orb empty-orb-warm"></div>
        <div>
          <strong>No files yet</strong>
          <p class="muted small">Upload a PDF and Subjectly will turn it into searchable notes.</p>
        </div>
      </div>
    `;
    return;
  }

  state.documents.forEach((doc) => {
    const card = document.createElement("div");
    card.className = "document-item";
    card.innerHTML = `
      <strong>${escapeHtml(doc.filename)}</strong>
      <div class="muted small">Indexed and ready for chat-based study.</div>
      <div class="document-actions">
        <a class="nav-pill" href="${doc.file_path}" target="_blank" rel="noreferrer">Open file</a>
      </div>
    `;
    documentsList.appendChild(card);
  });
}

function renderNotes() {
  notesContainer.innerHTML = "";
  if (!state.notes.length) {
    notesContainer.innerHTML = `
      <div class="empty-illustration">
        <div class="empty-orb"></div>
        <div>
          <strong>No notes extracted yet</strong>
          <p class="muted small">Uploaded PDFs will appear here as structured study notes.</p>
        </div>
      </div>
    `;
    return;
  }

  state.notes.forEach((note) => {
    const card = document.createElement("article");
    card.className = "note-card";
    card.innerHTML = `
      <div>
        <h3>${escapeHtml(note.title)}</h3>
        <p class="muted small">${escapeHtml(note.chapter || note.unit || "Structured note")}</p>
      </div>
      <p>${escapeHtml(note.content.slice(0, 420))}${note.content.length > 420 ? "..." : ""}</p>
    `;
    notesContainer.appendChild(card);
  });
}

function renderQuiz(questions) {
  state.quiz = questions;
  quizContainer.innerHTML = "";
  questions.forEach((question, index) => {
    const card = document.createElement("div");
    card.className = "quiz-card";
    const optionsHtml = question.type === "mcq"
      ? question.options.map((option) => `
          <label>
            <input type="radio" name="${question.id}" value="${escapeHtml(option)}">
            <span>${escapeHtml(option)}</span>
          </label>
        `).join("")
      : `<textarea data-answer="${question.id}" placeholder="Write your answer"></textarea>`;
    card.innerHTML = `
      <strong>Q${index + 1}. ${escapeHtml(question.prompt)}</strong>
      <div class="muted small">Topic: ${escapeHtml(question.topic)} · ${question.type.toUpperCase()}</div>
      <div class="quiz-options">${optionsHtml}</div>
    `;
    quizContainer.appendChild(card);
  });
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "ripple-btn";
  submit.textContent = "Evaluate Answers";
  submit.addEventListener("click", () => submitQuiz().catch(handleAsyncError));
  quizContainer.appendChild(submit);
}

async function loadSubjects() {
  state.subjects = await api("/subjects");
  if (!state.selectedSubjectId && state.subjects.length) {
    state.selectedSubjectId = state.subjects[0].id;
  }
  renderSubjects();
  updateSelectedSubjectLabel();
  await loadNotes();
}

async function loadNotes() {
  const query = state.selectedSubjectId ? `?subject_id=${state.selectedSubjectId}` : "";
  const data = await api(`/notes${query}`);
  state.notes = data.notes;
  state.documents = data.documents;
  renderNotes();
  renderDocuments();
  updateMetrics();
}

async function selectSubject(subjectId) {
  state.selectedSubjectId = subjectId;
  renderSubjects();
  updateSelectedSubjectLabel();
  await loadNotes();
}

async function createSubject(event) {
  event.preventDefault();
  const name = document.getElementById("subjectName").value.trim();
  const description = document.getElementById("subjectDescription").value.trim();
  if (!name) return;

  await api("/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  event.target.reset();
  await loadSubjects();
  showToast("Subject created.");
}

async function uploadPdf(event) {
  event.preventDefault();
  if (!state.selectedSubjectId) {
    showToast("Create or select a subject first.");
    return;
  }

  const file = document.getElementById("pdfFile").files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("subject_id", state.selectedSubjectId);
  formData.append("file", file);
  await api("/upload-pdf", { method: "POST", body: formData });
  event.target.reset();
  await loadSubjects();
  showToast("PDF uploaded successfully.");
}

async function askAI(event) {
  event.preventDefault();
  const rawQuestion = questionInput.value.trim();
  if (!rawQuestion) {
    showToast("Ask a question first.");
    return;
  }

  const userMessage = { role: "user", content: rawQuestion };
  state.chatHistory.push(userMessage);
  renderMessage(userMessage);
  saveChatHistory();
  updateMetrics();
  questionInput.value = "";
  autoResizeComposer();
  scrollChatToBottom();

  setThinking(true);
  try {
    const data = await api("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildQuestionPayload(rawQuestion)),
    });
    const assistantMessage = { role: "assistant", content: data.answer || "No answer returned." };
    state.chatHistory.push(assistantMessage);
    renderMessage(assistantMessage);
    saveChatHistory();
    updateMetrics();
    scrollChatToBottom();
  } catch (error) {
    console.error("Subjectly chat failed:", error);
    showToast(error.message || "AI request failed.");
  } finally {
    setThinking(false);
  }
}

async function generateQuiz() {
  if (!state.selectedSubjectId) {
    showToast("Select a subject first.");
    return;
  }
  const data = await api("/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id: state.selectedSubjectId, count: 6 }),
  });
  renderQuiz(data.questions);
}

async function submitQuiz() {
  const answers = {};
  state.quiz.forEach((question) => {
    if (question.type === "mcq") {
      const checked = document.querySelector(`input[name="${question.id}"]:checked`);
      answers[question.id] = checked ? checked.value : "";
    } else {
      const textarea = document.querySelector(`textarea[data-answer="${question.id}"]`);
      answers[question.id] = textarea ? textarea.value : "";
    }
  });

  const data = await api("/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject_id: state.selectedSubjectId,
      questions: state.quiz,
      answers,
    }),
  });

  quizContainer.innerHTML = `
    <div class="result-card">
      <h3>Score: ${data.score} / ${data.total_questions}</h3>
      <p class="muted small">Weak topics: ${escapeHtml(data.weak_topics.join(", ") || "None")}</p>
    </div>
  `;
  data.results.forEach((result) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.innerHTML = `
      <strong>${escapeHtml(result.topic)}</strong>
      <p class="muted small">Your answer: ${escapeHtml(result.user_answer || "No answer")}</p>
      <p class="muted small">Correct answer: ${escapeHtml(result.correct_answer)}</p>
      <p>${escapeHtml(result.explanation)}</p>
    `;
    quizContainer.appendChild(card);
  });
}

function clearChat() {
  state.chatHistory = [];
  saveChatHistory();
  renderChatHistory();
  showToast("Chat cleared.");
}

function bindModeButtons() {
  document.querySelectorAll(".mode-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.mode = button.dataset.mode;
      activeModeLabel.textContent = formatModeLabel(state.mode);
      updateMetrics();
    });
  });
}

function bindNavTracking() {
  const navLinks = [...document.querySelectorAll(".nav-pill[data-tab]")];
  const sections = navLinks
    .map((link) => document.getElementById(link.dataset.tab))
    .filter(Boolean);

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      navLinks.forEach((link) => link.classList.toggle("active", link.dataset.tab === entry.target.id));
    });
  }, { threshold: 0.35 });

  sections.forEach((section) => observer.observe(section));
}

function bindRippleEffects() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".ripple-btn");
    if (!button) return;
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
    button.appendChild(ripple);
    window.setTimeout(() => ripple.remove(), 550);
  });
}

function autoResizeComposer() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 260)}px`;
}

function handleAsyncError(error) {
  console.error("Subjectly action failed:", error);
  showToast(error.message || "Something went wrong.");
}

document.getElementById("subjectForm").addEventListener("submit", (event) => createSubject(event).catch(handleAsyncError));
document.getElementById("uploadForm").addEventListener("submit", (event) => uploadPdf(event).catch(handleAsyncError));
document.getElementById("chatForm").addEventListener("submit", askAI);
document.getElementById("generateTestBtn").addEventListener("click", () => generateQuiz().catch(handleAsyncError));
document.getElementById("refreshSubjects").addEventListener("click", () => loadSubjects().catch(handleAsyncError));
document.getElementById("clearChatBtn").addEventListener("click", clearChat);
questionInput.addEventListener("input", autoResizeComposer);

loadChatHistory();
renderChatHistory();
bindModeButtons();
bindNavTracking();
bindRippleEffects();
updateMetrics();

Promise.all([loadSubjects()]).catch(handleAsyncError);
