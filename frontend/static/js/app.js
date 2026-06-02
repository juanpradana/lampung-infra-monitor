/**
 * Lampung Infrastructure Monitor - Frontend JavaScript
 * Auth, API helpers, and UI utilities
 */

// ==================== Auth ====================
function getToken() {
    return localStorage.getItem('access_token');
}

function getUser() {
    try {
        return JSON.parse(localStorage.getItem('user'));
    } catch {
        return null;
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

function checkAuth() {
    const path = window.location.pathname;
    if (path === '/login') return;

    const token = getToken();
    if (!token) {
        window.location.href = '/login';
        return;
    }

    // Update UI with user info
    const user = getUser();
    if (user) {
        const nameEl = document.getElementById('userName');
        const avatarEl = document.getElementById('userAvatar');
        const infoEl = document.getElementById('userMenuInfo');
        const adminNav = document.getElementById('nav-admin');

        if (nameEl) nameEl.textContent = user.full_name || user.username;
        if (avatarEl) avatarEl.textContent = (user.full_name || user.username).charAt(0).toUpperCase();
        if (infoEl) infoEl.textContent = `${user.full_name || user.username} (${user.role})`;
        if (adminNav && user.role === 'superadmin') adminNav.classList.remove('hidden');
    }
}

// ==================== API Helpers ====================
async function apiGet(url) {
    const token = getToken();
    const resp = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
    });

    if (resp.status === 401) {
        logout();
        throw new Error('Session expired');
    }

    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    return resp.json();
}

async function apiPost(url, body) {
    const token = getToken();
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
    });

    if (resp.status === 401) {
        logout();
        throw new Error('Session expired');
    }

    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    return resp.json();
}

async function apiPut(url, body) {
    const token = getToken();
    const resp = await fetch(url, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
    });

    if (resp.status === 401) {
        logout();
        throw new Error('Session expired');
    }

    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    return resp.json();
}

async function apiDelete(url) {
    const token = getToken();
    const resp = await fetch(url, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`,
        },
    });

    if (resp.status === 401) {
        logout();
        throw new Error('Session expired');
    }

    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    return resp.json();
}

// ==================== Utilities ====================
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

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function formatRelativeTime(dateStr) {
    if (!dateStr) return '-';
    const now = new Date();
    const d = new Date(dateStr);
    const diff = Math.floor((now - d) / 1000);

    if (diff < 60) return 'Baru saja';
    if (diff < 3600) return `${Math.floor(diff / 60)} menit lalu`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} hari lalu`;
    return formatDate(dateStr);
}

// ==================== UI Helpers ====================
function showToast(message, type = 'info') {
    const colors = {
        info: 'bg-blue-500',
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
    };

    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 transition-all transform translate-y-0 opacity-100`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.transform = 'translateY(100px)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// User menu toggle
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();

    const menuBtn = document.getElementById('userMenuBtn');
    const menu = document.getElementById('userMenu');

    if (menuBtn && menu) {
        menuBtn.addEventListener('click', () => {
            menu.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!menuBtn.contains(e.target) && !menu.contains(e.target)) {
                menu.classList.add('hidden');
            }
        });
    }
});
