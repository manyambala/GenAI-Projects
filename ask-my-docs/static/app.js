const elements = {
    form: document.getElementById('askForm'),
    question: document.getElementById('question'),
    sendButton: document.getElementById('sendButton'),
    messages: document.getElementById('messages'),
    welcome: document.getElementById('welcome'),
    requestStatus: document.getElementById('requestStatus'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    documentStats: document.getElementById('documentStats')
};

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function setBusy(isBusy) {
    elements.sendButton.disabled = isBusy;
    elements.question.disabled = isBusy;
    elements.sendButton.textContent = isBusy ? 'Thinking...' : 'Ask';
    elements.requestStatus.textContent = isBusy ? 'Searching and checking your documents...' : '';
}

function scrollToLatest() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function addUserMessage(text) {
    const article = document.createElement('article');
    article.className = 'message user-message';
    article.innerHTML = `<div class="message-label">You</div><div class="bubble">${escapeHtml(text)}</div>`;
    elements.messages.appendChild(article);
    scrollToLatest();
}

function formatAnswer(answer, sources) {
    let content = escapeHtml(answer).replaceAll('\n', '<br>');
    const sourceIds = new Set(sources.map(source => String(source.id)));
    return content.replace(/\[(\d+)\]/g, (match, id) => {
        if (!sourceIds.has(id)) return match;
        return `<button type="button" class="citation" data-source-id="${id}" aria-label="Show source ${id}">${id}</button>`;
    });
}

function createSources(sources) {
    if (!sources.length) return '';
    return `
        <details class="sources">
            <summary>${sources.length} retrieved source${sources.length === 1 ? '' : 's'}</summary>
            <div class="source-list">
                ${sources.map(source => `
                    <article id="source-${escapeHtml(source.id)}" class="source-item">
                        <strong>[${escapeHtml(source.id)}] ${escapeHtml(source.title)}</strong>
                        <span>Score ${Number(source.score || 0).toFixed(3)}</span>
                        <p>${escapeHtml(source.text)}</p>
                    </article>
                `).join('')}
            </div>
        </details>`;
}

function addAssistantMessage(data) {
    const sources = Array.isArray(data.sources) ? data.sources : [];
    const article = document.createElement('article');
    article.className = 'message assistant-message';
    article.innerHTML = `
        <div class="message-label">Ask My Docs</div>
        <div class="bubble answer">${formatAnswer(data.answer, sources)}</div>
        <div class="answer-meta">
            ${Math.round(Number(data.latency_ms || 0))} ms
            <span>·</span>
            ${data.citation_validation?.all_valid ? 'Citations verified' : 'No verified citation'}
        </div>
        ${createSources(sources)}
    `;
    article.querySelectorAll('.citation').forEach(button => {
        button.addEventListener('click', () => {
            const details = article.querySelector('.sources');
            if (details) details.open = true;
            const source = article.querySelector(`#source-${button.dataset.sourceId}`);
            source?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            source?.classList.add('source-highlight');
            window.setTimeout(() => source?.classList.remove('source-highlight'), 1200);
        });
    });
    elements.messages.appendChild(article);
    scrollToLatest();
}

function addErrorMessage(message) {
    const article = document.createElement('article');
    article.className = 'message assistant-message';
    article.innerHTML = `
        <div class="message-label">Ask My Docs</div>
        <div class="bubble error">${escapeHtml(message)}</div>`;
    elements.messages.appendChild(article);
    scrollToLatest();
}

async function ask(question) {
    elements.welcome?.remove();
    addUserMessage(question);
    setBusy(true);

    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: question })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        addAssistantMessage(data);
    } catch (error) {
        addErrorMessage(`Unable to get an answer: ${error.message}`);
    } finally {
        setBusy(false);
        elements.question.focus();
    }
}

elements.form.addEventListener('submit', event => {
    event.preventDefault();
    const question = elements.question.value.trim();
    if (!question) return;
    elements.question.value = '';
    ask(question);
});

elements.question.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        elements.form.requestSubmit();
    }
});

document.querySelectorAll('[data-question]').forEach(button => {
    button.addEventListener('click', () => ask(button.dataset.question));
});

async function loadHealth() {
    try {
        const response = await fetch('/api/health', { cache: 'no-store' });
        if (!response.ok) throw new Error(`Health check failed (${response.status})`);
        const data = await response.json();
        const healthy = data.status === 'healthy';
        elements.statusDot.classList.toggle('healthy', healthy);
        elements.statusText.textContent = healthy ? 'Ready' : 'Not initialized';
        elements.documentStats.textContent = `${data.docs || 0} docs · ${data.chunks || 0} chunks`;
    } catch (error) {
        elements.statusText.textContent = 'Server unavailable';
        elements.documentStats.textContent = '';
    }
}

loadHealth();
elements.question.focus();
