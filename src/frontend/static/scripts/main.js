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

    // show a brief toast message that auto-disappears
    function showToast(message, durationMs = 3000) {
        const existing = document.querySelector('.toast-message');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'toast-message';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%);
            background: var(--primary-color); color: white; padding: 0.75rem 1.5rem;
            border-radius: var(--content-radius); font-size: 0.9rem;
            z-index: 10000; opacity: 0; transition: opacity 0.3s ease;
            max-width: 90vw; text-align: center;
        `;
        document.body.appendChild(toast);
        requestAnimationFrame(() => { toast.style.opacity = '1'; });
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, durationMs);
    }

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
            if (newAddress.error.includes("limit reached")) {
                showToast("Maximum 10 addresses reached — delete one first.");
            } else if (newAddress.error === "Unauthorized") {
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

        // Check if user is logged in and has the custom_email flag
        let userFlags = [];
        let userAddresses = [];
        let isLoggedIn = false;

        try {
            const meResponse = await fetch('/auth/me');
            const meData = await meResponse.json();
            if (meData.authenticated) {
                isLoggedIn = true;
                userFlags = meData.flags || [];
                userAddresses = meData.user?.addresses || [];

                // Fetch user's owned addresses
                const addrResponse = await fetch('/addresses');
                if (addrResponse.ok) {
                    const addrData = await addrResponse.json();
                    userAddresses = addrData.addresses || [];
                }
            }
        } catch (_) {
            // Not logged in or fetch failed — fall through
        }

        if (isLoggedIn && userFlags.includes('custom_email')) {
            // User has the custom_email flag — show both owned addresses and manual input
            const fields = [];

            if (userAddresses.length > 0) {
                fields.push({
                    name: "address_select",
                    label: "Your addresses",
                    type: "select",
                    options: userAddresses,
                    required: false
                });
            }

            fields.push({
                name: "email",
                label: `Or type a custom address (domains: ${acceptedDomains.join(", ")})`,
                type: "email",
                placeholder: `user@${acceptedDomains[0] || "example.com"}`,
                required: false
            });

            showModalForm(
                "Use Custom Email",
                fields,
                async (data) => {
                    let customEmail = (data.address_select || data.email || "").trim();
                    if (!customEmail) {
                        throw new Error("Select an address or type one.");
                    }

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
        } else if (isLoggedIn && userAddresses.length > 0) {
            // Logged in but no custom_email flag — show only owned addresses
            showModalForm(
                "Use Custom Email",
                [
                    {
                        name: "address_select",
                        label: "Your addresses",
                        type: "select",
                        options: userAddresses,
                        required: true
                    }
                ],
                async (data) => {
                    updateEmail(data.address_select);
                },
                "Use"
            );
        } else if (isLoggedIn) {
            // Logged in but no addresses and no custom_email flag — nothing to show
            showModalForm(
                "Use Custom Email",
                [
                    {
                        name: "info",
                        label: "",
                        type: "text",
                        placeholder: "No addresses yet — generate one first.",
                        required: false,
                        readonly: true
                    }
                ],
                async () => {},
                "Close"
            );
        } else {
            // Guest — not allowed
            showModalForm(
                "Use Custom Email",
                [
                    {
                        name: "info",
                        label: "",
                        type: "text",
                        placeholder: "Log in to use custom addresses.",
                        required: false,
                        readonly: true
                    }
                ],
                async () => {},
                "Close"
            );
        }
    }

    // shows a form to the user
    function showModalForm(title, fields, onSubmit, submitLabel = "Send") {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        const fieldsHtml = fields.map(field => {
            if (field.type === "select") {
                const options = (field.options || []).map(o =>
                    `<option value="${o}">${o}</option>`
                ).join('');
                return `
                <div class="form-group">
                    <label for="${field.name}">${field.label}</label>
                    <select id="${field.name}" name="${field.name}" class="form-control" ${field.required ? 'required' : ''}>
                        ${options}
                    </select>
                </div>`;
            }
            return `
            <div class="form-group">
                <label for="${field.name}">${field.label}</label>
                <input type="${field.type}" id="${field.name}" name="${field.name}" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''} ${field.readonly ? 'readonly' : ''}>
            </div>`;
        }).join('');

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
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
        <div class="modal-content" style="max-width: 400px; text-align: center;">
            <div class="modal-header">
                <h2>Settings</h2>
            </div>
            <p style="color: var(--text-dark-color); margin: 1.5rem 0;">
                Not logged in — <a href="/auth/login" style="color: var(--primary-color);">Log in</a>
                or <a href="/auth/register" style="color: var(--primary-color);">Register</a>
                to manage API keys.
            </p>
            <div class="modal-actions" style="justify-content: center;">
                <button type="button" class="btn btn-primary" id="settings-close-btn">Close</button>
            </div>
        </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#settings-close-btn').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
    }

    function showSettingsLoggedIn(userData) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
        <div class="modal-content" style="max-width: 440px;">
            <div class="modal-header">
                <h2>Settings</h2>
                <button type="button" id="settings-close-btn" style="background: none; border: none; color: var(--text-dark-color); cursor: pointer; padding: 0.25rem; display: flex; align-items: center; border-radius: 4px;" title="Close">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="form-group">
                <label for="settings-apikey">API Key</label>
                <div style="display: flex; gap: 0.5rem;">
                    <input type="text" id="settings-apikey" class="form-control" readonly style="user-select: all; flex: 1;">
                    <button type="button" class="btn btn-secondary" id="settings-copy-key" title="Copy API key to clipboard" style="width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                    <button type="button" class="btn btn-secondary" id="settings-regenerate-key" title="Revoke current key and generate a new one" style="width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                    </button>
                </div>
            </div>
            <div style="margin-top: 1rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
                <label style="font-size: 0.85rem; color: var(--text-dark-color); display: block; margin-bottom: 0.5rem;">Your Addresses (<span id="settings-addr-count">0</span>/10)</label>
                <div id="settings-address-list" style="max-height: 200px; overflow-y: auto;"></div>
            </div>
            <p id="settings-status" style="color: var(--text-dark-color); font-size: 0.8rem; margin-top: 0.75rem; min-height: 1.2em; text-align:center;"></p>
        </div>`;

        document.body.appendChild(overlay);

        // Set values — use the key from the server response
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
            regenBtn.style.opacity = '0.5';
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
                    statusEl.textContent = 'New key generated — old key has been revoked';
                    statusEl.style.color = 'var(--primary-color)';
                } else {
                    statusEl.textContent = data.error || 'Failed to regenerate';
                }
            } catch (err) {
                statusEl.textContent = 'Error regenerating key';
            }

            regenBtn.disabled = false;
            regenBtn.style.opacity = '1';
        });

        // Fetch and display user's addresses
        loadAddressList(overlay);
    }

    async function loadAddressList(overlay) {
        try {
            const response = await fetch('/addresses');
            const data = await response.json();
            const list = overlay.querySelector('#settings-address-list');
            const count = overlay.querySelector('#settings-addr-count');
            if (!list) return;

            const addresses = data.addresses || [];
            if (count) count.textContent = addresses.length;

            if (addresses.length === 0) {
                list.innerHTML = '<div style="color: var(--text-dark-color); font-size: 0.85rem; padding: 0.5rem 0;">No addresses yet — generate one from the main page.</div>';
                return;
            }

            list.innerHTML = addresses.map(addr => `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border-color);">
                    <span style="font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">${addr}</span>
                    <button class="btn-delete-address" data-address="${addr}" title="Delete this address" style="background: none; border: none; color: var(--text-dark-color); cursor: pointer; padding: 0.25rem; border-radius: 4px; flex-shrink: 0; display: flex; align-items: center;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            `).join('');

            list.querySelectorAll('.btn-delete-address').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const addr = btn.dataset.address;

                    // Confirmation modal — styled to match settings
                    const confirmOverlay = document.createElement('div');
                    confirmOverlay.className = 'modal-overlay';
                    confirmOverlay.innerHTML = `
                    <div class="modal-content" style="max-width: 400px;">
                        <div class="modal-header">
                            <h2>Delete Address</h2>
                            <button type="button" class="modal-close-btn" style="background: none; border: none; color: var(--text-dark-color); cursor: pointer; padding: 0.25rem; display: flex; align-items: center; border-radius: 4px;" title="Cancel">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </div>
                        <p style="color: var(--text-dark-color); margin: 1rem 0; font-size: 0.9rem;">
                            Delete <strong style="color: var(--text-color);">${escapeHtml(addr)}</strong>? This cannot be undone.
                        </p>
                        <div class="form-group">
                            <label for="confirm-delete-input">Type <strong>DELETE</strong> to confirm</label>
                            <input type="text" id="confirm-delete-input" class="form-control" placeholder="DELETE" required>
                        </div>
                        <div class="modal-actions" style="justify-content: flex-end; gap: 0.5rem;">
                            <button type="button" class="btn btn-secondary" id="confirm-cancel-btn">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirm-delete-btn" disabled style="background-color: #e74c3c;">Delete</button>
                        </div>
                        <p id="confirm-delete-status" style="color: #e74c3c; font-size: 0.8rem; margin-top: 0.5rem; min-height: 1.2em; text-align: center;"></p>
                    </div>`;
                    document.body.appendChild(confirmOverlay);

                    const confirmInput = confirmOverlay.querySelector('#confirm-delete-input');
                    const deleteBtn = confirmOverlay.querySelector('#confirm-delete-btn');
                    const cancelBtn = confirmOverlay.querySelector('#confirm-cancel-btn');
                    const closeX = confirmOverlay.querySelector('.modal-close-btn');
                    const statusEl = confirmOverlay.querySelector('#confirm-delete-status');

                    function closeConfirm() {
                        confirmOverlay.remove();
                    }

                    confirmInput.addEventListener('input', () => {
                        deleteBtn.disabled = confirmInput.value.trim() !== 'DELETE';
                    });

                    confirmInput.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !deleteBtn.disabled) deleteBtn.click();
                        if (e.key === 'Escape') closeConfirm();
                    });

                    deleteBtn.addEventListener('click', async () => {
                        deleteBtn.disabled = true;
                        deleteBtn.textContent = 'Deleting...';
                        statusEl.textContent = '';
                        try {
                            const delResponse = await fetch(`/addresses/${encodeURIComponent(addr)}`, { method: 'DELETE' });
                            const delData = await delResponse.json();
                            if (delData.message) {
                                showToast('Address deleted');
                                closeConfirm();
                                loadAddressList(overlay);
                            } else {
                                throw new Error(delData.error || 'Failed to delete address');
                            }
                        } catch (err) {
                            statusEl.textContent = err.message;
                            deleteBtn.disabled = false;
                            deleteBtn.textContent = 'Delete';
                        }
                    });

                    cancelBtn.addEventListener('click', closeConfirm);
                    closeX.addEventListener('click', closeConfirm);
                    confirmOverlay.addEventListener('click', (e) => {
                        if (e.target === confirmOverlay) closeConfirm();
                    });
                });
            });
        } catch (err) {
            // Address list failed to load — not critical
        }
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
