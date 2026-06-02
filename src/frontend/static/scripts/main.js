document.addEventListener("DOMContentLoaded", () => {
    // make variables
    let currentEmail = "";
    let currentInbox = [];

    // make element references
    const emailInput = document.getElementById('email-input');
    const randomBtn = document.getElementById('random-btn');
    const customBtn = document.getElementById('custom-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const copyBtn = document.getElementById('copy-btn');
    const inboxList = document.getElementById('inbox-list');
    const placeholder = document.getElementById('inbox-placeholder');
    const sendBtn = document.getElementById('send-btn');
    const settingsBtn = document.getElementById('settings-btn');

    // add event listeners
    copyBtn.addEventListener('click', copyToClipboard);
    randomBtn.addEventListener('click', generateRandomEmail);
    refreshBtn.addEventListener('click', fetchInbox);
    customBtn.addEventListener('click', handleCustomEmail);
    if (sendBtn) {
        sendBtn.addEventListener('click', sendButtonClicked); 
    }
    if (settingsBtn) {
        settingsBtn.addEventListener('click', showSettings);
    }

    // function definitions

    // HTML-escape untrusted text to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    // copy email to clipboard
    function copyToClipboard() {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(emailInput.value).catch(() => {
                // Fallback
                emailInput.select();
                document.execCommand('copy');
            });
        } else {
            emailInput.select();
            document.execCommand('copy');
        }

        // Show copied state on the button
        const originalText = copyBtn.querySelector('.button-text').textContent;
        copyBtn.querySelector('.button-text').textContent = 'Copied!';
        copyBtn.classList.add('copied');

        // Reset after 2 seconds
        setTimeout(() => {
            copyBtn.querySelector('.button-text').textContent = originalText;
            copyBtn.classList.remove('copied');
        }, 2000);
    }

    // generate random email and assign it as the current email
    async function generateRandomEmail() {
        const newAddress = await getRandomAddress();
        if (newAddress.error) {
            // If we get an auth error, the user needs to log in to get an API key
            // but the guest endpoint should work — show a generic error
            if (newAddress.error === "Unauthorized") {
                // Guest mode: the endpoint should work without auth
                // If it fails, something else is wrong
                console.error("Failed to get random address:", newAddress.error);
            }
            return;
        }
        updateEmail(newAddress.address);
    }

    // update the current email
    function updateEmail(email) {
        currentEmail = email;
        emailInput.value = email;
        fetchInbox();
    }
    
    // check if inboxes are different
    function haveInboxesChanged(oldInbox, newInbox) {
        if (oldInbox.length !== newInbox.length) {
            return true;
        }

        const oldEmailIds = new Set(oldInbox.map(email => email.Timestamp));
        const hasNewEmail = newInbox.some(email => !oldEmailIds.has(email.Timestamp));
        return hasNewEmail;
    }

    // format time
    function formatTime(timestamp) {
        const now = Math.floor(Date.now() / 1000);

        const secondsAgo = now - timestamp;

        const minute = 60;
        const hour = minute * 60;
        const day = hour * 24;

        if (secondsAgo >= day) {
            const days = Math.floor(secondsAgo / day);
            return `${days} days ago`;
        } else if (secondsAgo >= hour) {
            const hours = Math.floor(secondsAgo / hour);
            return `${hours} hours ago`;
        } else if (secondsAgo >= minute) {
            const minutes = Math.floor(secondsAgo / minute);
            return `${minutes} minutes ago`;
        } else {
            return `${secondsAgo} seconds ago`;
        }
    }

    // fetch the inbox from the server
    async function fetchInbox() {
        if (!currentEmail) return;

        refreshBtn.classList.add('loading');

        let newInbox = await getInbox(currentEmail);

        if (newInbox && newInbox.error === "Unauthorized") {
            refreshBtn.classList.remove('loading');
            return;
        }

        if (!newInbox || newInbox.error) {
            refreshBtn.classList.remove('loading');
            return;
        }

        if (haveInboxesChanged(currentInbox, newInbox)) {
            currentInbox = newInbox;
            renderInbox();
        }

        refreshBtn.classList.remove('loading');
    }

    // render the inbox
    function renderInbox() {
        inboxList.innerHTML = '';

        if (currentInbox.length === 0) {
            placeholder.style.display = 'block';
            return;
        }

        placeholder.style.display = 'none';

        currentInbox.forEach(email => {
            const emailItem = document.createElement('li');
            emailItem.className = 'email-item';

            const summary = document.createElement('div');
            summary.className = 'email-summary';

            const from = document.createElement('span');
            from.className = 'email-from';
            from.textContent = email.From;

            const subject = document.createElement('span');
            subject.className = 'email-subject';
            subject.textContent = email.Subject || '(no subject)';

            const time = document.createElement('span');
            time.className = 'email-time';
            time.textContent = formatTime(email.Timestamp);

            summary.appendChild(from);
            summary.appendChild(subject);
            summary.appendChild(time);

            const body = document.createElement('div');
            body.className = 'email-body';

            const iframe = document.createElement('iframe');
            iframe.className = 'email-body-iframe';
            body.appendChild(iframe);

            summary.addEventListener('click', () => {
                emailItem.classList.toggle('open');
                const iframe = emailItem.querySelector('.email-body-iframe');
                if (emailItem.classList.contains('open')) {
                    // Wrap body in a styled document so text is readable
                    // on the dark background
                    iframe.srcdoc = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Roboto Mono', monospace;
        font-size: 14px;
        line-height: 1.6;
        padding: 1rem;
        margin: 0;
    }
    a { color: #9b6fc0; }
    img { max-width: 100%; height: auto; }
    pre, code { background-color: #2a2a2a; padding: 0.2em 0.4em; border-radius: 3px; }
    pre { padding: 1rem; overflow-x: auto; }
    blockquote { border-left: 3px solid #9b6fc0; margin: 0; padding-left: 1rem; color: #aaa; }
</style>
</head>
<body>${escapeHtml(email.Body)}</body>
</html>`;
                }
            });

            emailItem.appendChild(summary);
            emailItem.appendChild(body);
            inboxList.appendChild(emailItem);
        });
    }

    // use a custom email address — must be on an accepted domain
    async function handleCustomEmail() {
        // Fetch accepted domains from the server
        const domainData = await getDomains();
        const acceptedDomains = domainData.domains || [];

        showModalForm(
            "Use Custom Email",
            [
                {
                    name: "email",
                    label: `Email address (accepted domains: ${acceptedDomains.join(", ")})`,
                    type: "email",
                    placeholder: `user@${acceptedDomains[0] || "example.com"}`,
                    required: true
                }
            ],
            async (data) => {
                let customEmail = data.email.trim();
                if (!customEmail) return;

                if (!customEmail.includes("@")) {
                    customEmail = customEmail + "@" + acceptedDomains[0];
                    updateEmail(customEmail);
                    return;
                }

                const domainPart = customEmail.split("@")[1].toLowerCase();
                if (!acceptedDomains.some(d => d.toLowerCase() === domainPart)) {
                    throw new Error(
                        `"${domainPart}" is not an accepted domain.\nAccepted domains: ${acceptedDomains.join(", ")}`
                    );
                }

                updateEmail(customEmail);
            },
            "Use"
        );
    }

    // shows a form to the user
    function showModalForm(title, fields, onSubmit, submitLabel = "Send") {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        const fieldsHtml = fields.map(field => `
        <div class="form-group">
            <label for="${field.name}">${field.label}</label>
            <input type="${field.type}" id="${field.name}" name="${field.name}" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''} ${field.readonly ? 'readonly' : ''}>
        </div>`).join('');

        overlay.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
            </div>
            <form id="dynamic-modal-form">
                ${fieldsHtml}
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" id="modal-cancel-btn">
                        Cancel
                    </button>
                    <button type="submit" class="btn btn-primary">
                        ${submitLabel}
                    </button>
                </div>
            </form>
        </div>`;

        document.body.appendChild(overlay);

        const form = overlay.querySelector('#dynamic-modal-form');
        const cancelBtn = overlay.querySelector('#modal-cancel-btn');

        function close() {
            overlay.remove();
        }

        cancelBtn.addEventListener('click', close);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close();
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const data = {};
            fields.forEach(field => {
                data[field.name] = document.getElementById(field.name).value;
            });

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.innerHTML = `${submitLabel}..`;

            try {
                await onSubmit(data);
                close();
            } catch (error) {
                // Show error inline in the modal instead of alert
                const existingError = overlay.querySelector('.modal-error');
                if (existingError) existingError.remove();

                const errorEl = document.createElement('p');
                errorEl.className = 'modal-error';
                errorEl.textContent = error.message;
                overlay.querySelector('.modal-actions').before(errorEl);

                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // settings modal — shows API key if logged in
    function showSettings() {
        // Fetch the current API key info from the server
        fetch('/auth/me')
            .then(r => r.json())
            .then(data => {
                if (data.authenticated) {
                    // Logged in — show API key management
                    showSettingsLoggedIn(data);
                } else {
                    // Guest — show login prompt
                    showSettingsGuest();
                }
            })
            .catch(() => showSettingsGuest());
    }

    function showSettingsGuest() {
        showModalForm(
            "Settings",
            [
                { name: "info", label: "Status", type: "text", placeholder: "", required: false, readonly: true }
            ],
            async () => {},
            "Close"
        );
        setTimeout(() => {
            const el = document.getElementById('info');
            if (el) el.value = 'Not logged in — log in to manage API keys';
        }, 50);
    }

    function showSettingsLoggedIn(userData) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Settings</h2>
            </div>
            <div class="form-group">
                <label for="settings-email">Account</label>
                <input type="text" id="settings-email" readonly style="user-select: all;">
            </div>
            <div class="form-group">
                <label for="settings-apikey">API Key</label>
                <input type="text" id="settings-apikey" readonly style="user-select: all;">
            </div>
            <div class="modal-actions" style="justify-content: space-between;">
                <button type="button" class="btn btn-secondary" id="settings-copy-key">Copy Key</button>
                <div>
                    <button type="button" class="btn btn-primary" id="settings-regenerate-key">Regenerate</button>
                    <button type="button" class="btn btn-secondary" id="settings-close-btn">Close</button>
                </div>
            </div>
            <p id="settings-status" style="color: var(--text-dark-color); font-size: 0.8rem; margin-top: 0.5rem;"></p>
        </div>`;

        document.body.appendChild(overlay);

        // Set values via textContent-safe properties (prevents XSS from user-controlled email)
        document.getElementById('settings-email').value = userData.email || '';
        document.getElementById('settings-apikey').value = userData.api_key || 'No API key';

        const closeBtn = overlay.querySelector('#settings-close-btn');
        const copyBtn = overlay.querySelector('#settings-copy-key');
        const regenBtn = overlay.querySelector('#settings-regenerate-key');
        const statusEl = overlay.querySelector('#settings-status');

        closeBtn.addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        copyBtn.addEventListener('click', () => {
            const keyInput = document.getElementById('settings-apikey');
            const text = keyInput.value;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).catch(() => {
                    keyInput.select();
                    document.execCommand('copy');
                });
            } else {
                keyInput.select();
                document.execCommand('copy');
            }
            statusEl.textContent = 'Copied!';
            setTimeout(() => { statusEl.textContent = ''; }, 2000);
        });

        regenBtn.addEventListener('click', async () => {
            regenBtn.disabled = true;
            regenBtn.textContent = 'Regenerating...';
            statusEl.textContent = '';

            try {
                const response = await fetch('/auth/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });
                const data = await response.json();
                if (data.api_key) {
                    document.getElementById('settings-apikey').value = data.api_key;
                    setApiKey(data.api_key);
                    statusEl.textContent = 'New key generated — save it now, it won\'t be shown again';
                    statusEl.style.color = '#e74c3c';
                } else {
                    statusEl.textContent = data.error || 'Failed to regenerate';
                }
            } catch (err) {
                statusEl.textContent = 'Error regenerating key';
            }

            regenBtn.disabled = false;
            regenBtn.textContent = 'Regenerate';
        });
    }

    // send button clicked
    async function sendButtonClicked() {
        showModalForm(
            "Send Email",
            [
                { name: "from", label: "From", type: "email", placeholder: currentEmail, required: true },
                { name: "to", label: "To", type: "email", placeholder: "example@example.com", required: true },
                { name: "subject", label: "Subject", type: "text", placeholder: "Subject", required: true },
                { name: "body", label: "Body", type: "text", placeholder: "Message body", required: true }
            ],
            async (data) => {
                const result = await sendEmail(data.from, data.to, data.subject, data.body);
                if (result.error) {
                    throw new Error(result.error);
                }
                // Show success state on the send button briefly
                const sendBtn = document.getElementById('send-btn');
                const originalText = sendBtn.querySelector('.button-text').textContent;
                sendBtn.querySelector('.button-text').textContent = 'Sent!';
                sendBtn.classList.add('copied');
                setTimeout(() => {
                    sendBtn.querySelector('.button-text').textContent = originalText;
                    sendBtn.classList.remove('copied');
                }, 2000);
            }
        );
    }

    // generate an email when the page loads
    (async () => {
        await generateRandomEmail();
    })();

    // automatic inbox refreshing
    setInterval(fetchInbox, 5000);
});
