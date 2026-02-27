// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Update current time
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        updateTime();
        setInterval(updateTime, 1000);
    }

    // Setup form handlers
    setupSettingsForm();
    setupTargetForm();
    setupEngineControl();
    setupManualRun();
    setupTestButtons();
    setupFilters();

    // Load targets on page load
    loadTargets();

    // Check for flash messages
    checkFlashMessages();
});

function updateTime() {
    const now = new Date();
    const options = { 
        year: 'numeric', 
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        timeZoneName: 'short'
    };
    const timeEl = document.getElementById('current-time');
    if (timeEl) {
        timeEl.textContent = now.toLocaleDateString(undefined, options);
    }
}

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#007cba'};
        color: white;
        padding: 15px 20px;
        border-radius: 4px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 1000;
        max-width: 300px;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Settings Form
function setupSettingsForm() {
    const form = document.getElementById('settings-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);

        const response = await fetch('/settings/api', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification('Settings saved successfully!', 'success');
        } else {
            const errorMsg = data.detail || data.message || JSON.stringify(data);
            showNotification(`Failed to save settings: ${errorMsg}`, 'error');
        }
    });
}

// Target Form
function setupTargetForm() {
    const form = document.getElementById('add-target-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const industry = document.getElementById('industry').value.trim();
        const country = document.getElementById('country').value.trim();
        const state = document.getElementById('state').value.trim() || null;

        if (!industry || !country) {
            showNotification('Industry and country are required', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('industry', industry);
        formData.append('country', country);
        if (state) formData.append('state', state);

        const response = await fetch('/targets/api', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification('Target added successfully!', 'success');
            form.reset();
            loadTargets();
        } else {
            const errorMsg = data.detail || data.message || JSON.stringify(data);
            showNotification(`Failed to add target: ${errorMsg}`, 'error');
        }
    });

    // Delete target buttons (event delegation)
    document.addEventListener('click', async function(e) {
        if (e.target.classList.contains('delete-target')) {
            if (!confirm('Are you sure you want to delete this target?')) {
                return;
            }

            const targetId = e.target.dataset.id;
            
            const response = await fetch(`/targets/api/${targetId}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            
            if (response.ok) {
                showNotification('Target deleted successfully!', 'success');
                loadTargets();
            } else {
                const errorMsg = data.detail || data.message || JSON.stringify(data);
                showNotification(`Failed to delete target: ${errorMsg}`, 'error');
            }
        }
    });
}

// Load Targets Function
async function loadTargets() {
    const tbody = document.querySelector('#targets-table tbody');
    if (!tbody) return;

    try {
        const response = await fetch('/targets/api');
        const data = await response.json();
        
        tbody.innerHTML = '';
        
        if (!data.targets || data.targets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="no-data">No targets configured yet</td></tr>';
            return;
        }
        
        data.targets.forEach(target => {
            const row = document.createElement('tr');
            row.setAttribute('data-id', target.id);
            row.innerHTML = `
                <td>${target.industry}</td>
                <td>${target.country}</td>
                <td>${target.state || '-'}</td>
                <td>
                    <button class="btn btn-danger btn-small delete-target" 
                            data-id="${target.id}"
                            title="Delete target">
                        🗑️
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Failed to load targets:', error);
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">Failed to load targets</td></tr>';
    }
}

// Engine Control
function setupEngineControl() {
    const form = document.getElementById('engine-control-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const action = e.submitter.value;
        const formData = new FormData();
        formData.append('action', action);
        
        const response = await fetch('/campaign/api/control', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification(`Engine ${action === 'start' ? 'started' : 'stopped'} successfully!`, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            const errorMsg = data.detail || data.message || JSON.stringify(data);
            showNotification(`Failed to control engine: ${errorMsg}`, 'error');
        }
    });
}

// Manual Run
function setupManualRun() {
    const button = document.getElementById('manual-run');
    if (!button) return;

    button.addEventListener('click', async function() {
        if (!confirm('Trigger manual engine execution now?')) {
            return;
        }

        const response = await fetch('/campaign/api/run', {
            method: 'POST'
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification('Manual execution triggered!', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            const errorMsg = data.detail || data.message || JSON.stringify(data);
            showNotification(`Failed to start manual run: ${errorMsg}`, 'error');
        }
    });
}

// Test Buttons
function setupTestButtons() {
    const testSmtp = document.getElementById('test-smtp');
    const testTelegram = document.getElementById('test-telegram');

    if (testSmtp) {
        testSmtp.addEventListener('click', async function() {
            const response = await fetch('/settings/test/smtp');
            const data = await response.json();
            
            if (response.ok) {
                showNotification('SMTP test successful! Check your inbox.', 'success');
            } else {
                const errorMsg = data.detail || data.message || JSON.stringify(data);
                showNotification(`SMTP test failed: ${errorMsg}`, 'error');
            }
        });
    }

    if (testTelegram) {
        testTelegram.addEventListener('click', async function() {
            const response = await fetch('/settings/test/telegram');
            const data = await response.json();
            
            if (response.ok) {
                showNotification('Telegram test message sent!', 'success');
            } else {
                const errorMsg = data.detail || data.message || JSON.stringify(data);
                showNotification(`Telegram test failed: ${errorMsg}`, 'error');
            }
        });
    }
}

// Filters
function setupFilters() {
    const filters = ['status-filter', 'industry-filter', 'country-filter', 'priority-filter'];
    
    filters.forEach(filterId => {
        const filter = document.getElementById(filterId);
        if (!filter) return;

        filter.addEventListener('input', debounce(applyFilters, 300));
    });
}

function applyFilters() {
    const status = document.getElementById('status-filter')?.value?.toLowerCase() || '';
    const industry = document.getElementById('industry-filter')?.value?.toLowerCase() || '';
    const country = document.getElementById('country-filter')?.value?.toLowerCase() || '';
    const priority = parseInt(document.getElementById('priority-filter')?.value) || 0;

    const rows = document.querySelectorAll('#leads-table tbody tr');
    
    rows.forEach(row => {
        if (!row.dataset.id) return;
        
        const rowStatus = row.querySelector('td:nth-child(8)')?.textContent.toLowerCase() || '';
        const rowIndustry = row.querySelector('td:nth-child(3)')?.textContent.toLowerCase() || '';
        const rowCountry = row.querySelector('td:nth-child(4)')?.textContent.toLowerCase() || '';
        const rowPriority = parseInt(row.querySelector('td:nth-child(9)')?.textContent) || 0;
        
        const matchesStatus = !status || rowStatus.includes(status);
        const matchesIndustry = !industry || rowIndustry.includes(industry);
        const matchesCountry = !country || rowCountry.includes(country);
        const matchesPriority = rowPriority >= priority;
        
        row.style.display = matchesStatus && matchesIndustry && matchesCountry && matchesPriority ? '' : 'none';
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function checkFlashMessages() {
    const urlParams = new URLSearchParams(window.location.search);
    const msg = urlParams.get('msg');
    const type = urlParams.get('type') || 'info';
    
    if (msg) {
        showNotification(decodeURIComponent(msg), type);
        
        const newUrl = new URL(window.location);
        newUrl.searchParams.delete('msg');
        newUrl.searchParams.delete('type');
        window.history.replaceState({}, '', newUrl);
    }
}
