// API key management (for programmatic access)
// Stored in sessionStorage (cleared on tab close) rather than localStorage
// to limit exposure if the browser is left unattended.
function getApiKey() {
    return sessionStorage.getItem('md_api_key');
}

function setApiKey(key) {
    sessionStorage.setItem('md_api_key', key);
}

function clearApiKey() {
    sessionStorage.removeItem('md_api_key');
}

function authHeaders() {
    const key = getApiKey();
    return key ? { 'Authorization': `Bearer ${key}` } : {};
}

// get the inbox from the server
async function getInbox(address, password = null) {
    const headers = { ...authHeaders() };

    if (password) {
        headers["Authorization"] = password;
    }

    const response = await fetch(`/get_inbox?address=${address}`, { headers });

    if (response.status === 401) {
        return { error: "Unauthorized" };
    }

    return await response.json();
}

// get a random email from the server
async function getRandomAddress() {
    const response = await fetch('/get_random_address');
    
    if (response.status === 401) {
        return { error: "Unauthorized" };
    }

    return await response.json();
}

// get the accepted domains from the server
async function getDomains() {
    const response = await fetch('/get_domain');
    
    return await response.json();
}

// send an email
async function sendEmail(fromAddress, toAddress, subject, body) {
    const response = await fetch('/send_email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            From: fromAddress,
            To: toAddress,
            Subject: subject,
            Body: body
        })
    });

    return await response.json();
}
