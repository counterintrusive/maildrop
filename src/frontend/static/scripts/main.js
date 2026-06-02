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

    // add event listeners
    copyBtn.addEventListener('click', copyToClipboard);
    randomBtn.addEventListener('click', generateRandomEmail);
    refreshBtn.addEventListener('click', fetchInbox);
    customBtn.addEventListener('click', handleCustomEmail);
    if (sendBtn) {
        sendBtn.addEventListener('click', sendButtonClicked); 
    }

    // function defnitions

    // copy email to clipboard
    function copyToClipboard() {
        emailInput.select();
        document.execCommand('copy');

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

        let password = localStorage.getItem(`${currentEmail}-password`);
        let newInbox = await getInbox(currentEmail, password);

        if (newInbox.error === "Unauthorized") {
            password = prompt("Enter password:");
            if (password) {
                localStorage.setItem(`${currentEmail}-password`, password);
                newInbox = await getInbox(currentEmail, password);
                if (newInbox.error === "Unauthorized") {
                    await generateRandomEmail();
                }
            } else {
                await generateRandomEmail();
            }
        }

        if (haveInboxesChanged(currentInbox, newInbox)) {
            renderInbox(newInbox);
        }

        currentInbox = newInbox;

        refreshBtn.classList.remove('loading');
    }

    // render the inbox in the inbox element
    function renderInbox(inbox) {
        inboxList.innerHTML = '';
        if (inbox && inbox.length > 0) {
            placeholder.style.display = 'none';
            inbox.forEach(email => {
                const emailItem = document.createElement('li');
                emailItem.className = 'email-item';
                emailItem.innerHTML = `
                    <div class="email-summary">
                        <div class="email-details">
                            <div class="sender">${email.From}</div>
                            <div class="subject">${email.Subject}</div>
                        </div>
                        <div class="time">${formatTime(email.Timestamp)}</div>
                    </div>
                    <div class="email-body">
                        <iframe class="email-body-iframe" srcdoc=""></iframe>
                    </div>
                `;
                inboxList.appendChild(emailItem);

                const summary = emailItem.querySelector('.email-summary');
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
<body>${email.Body}</body>
</html>`;
                    }
                });
            });
        } else {
            placeholder.style.display = 'block';
        }
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
            ${field.multiline
                ? `<textarea id="${field.name}" name="${field.name}" class="form-control" rows="5" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''}>${field.value || ''}</textarea>`
                : `<input type="${field.type || 'text'}" id="${field.name}" name="${field.name}" class="form-control" value="${field.value || ''}" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''} ${field.readonly ? 'readonly' : ''}>`
            }
        </div>`).join('');

        overlay.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
            </div>
            <form id="dynamic-modal-form">
                ${fieldsHtml}
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary cancel-btn">Cancel</button>
                    <button type="submit" class="btn btn-primary">
                        ${submitLabel}
                    </button>
                </div>
            </form>
        </div>`;

        document.body.appendChild(overlay);

        const close = () => document.body.removeChild(overlay);

        overlay.querySelector('.cancel-btn').onclick = close;

        overlay.querySelector('form').onsubmit = async (event) => {
            event.preventDefault();
            const submitBtn = overlay.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = `${submitLabel}..`;

            const formData = new FormData(event.target);
            const data = Object.fromEntries(formData.entries());

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
        };
    }

    // when send button is clicked show the form
    function sendButtonClicked() {
        const formData = [
            {
                name: "from",
                label: "From",
                value: currentEmail,
                readonly: true
            },
            {
                name: "to",
                label: "To",
                type: "email",
                placeholder: "example@example.com",
                required: true
            },
            {
                name: "subject",
                label: "Subject",
                placeholder: "Email subject",
                required: true
            },
            {
                name: "body",
                label: "Message",
                multiline: true,
                required: true,
                placeholder: "Main email body"
            }
        ]
        showModalForm(
            "Send Email",
            formData,
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
