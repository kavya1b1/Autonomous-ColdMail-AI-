/* ============================================================
   Thin fetch wrapper around the ColdMail AI Pro FastAPI backend.
   ============================================================ */
const API_BASE = '/api';
const TOKEN_KEY = 'coldmail_token';

const Auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
  },
};

async function apiRequest(path, { method = 'GET', body, isForm = false, skipAuth = false } = {}) {
  const opts = { method, headers: {} };

  if (!skipAuth) {
    const token = Auth.getToken();
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  }

  if (body !== undefined) {
    if (isForm) {
      opts.body = body; // FormData sets its own headers
    } else {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, opts);
  } catch (networkErr) {
    throw new ApiError('Could not reach the server. Check your connection and try again.', 0);
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!res.ok) {
    if (res.status === 401 && !skipAuth) {
      Auth.clear();
      if (typeof onSessionExpired === 'function') onSessionExpired();
    }
    const detail = (data && typeof data === 'object' && 'detail' in data) ? data.detail : (data || res.statusText);
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status);
  }

  return data;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const Api = {
  // Auth
  signup: (payload) => apiRequest('/auth/signup', { method: 'POST', body: payload, skipAuth: true }),
  login: (payload) => apiRequest('/auth/login', { method: 'POST', body: payload, skipAuth: true }),
  logout: () => apiRequest('/auth/logout', { method: 'POST' }),
  me: () => apiRequest('/auth/me'),

  // Profile
  getProfile: () => apiRequest('/profile'),
  saveProfile: (profile) => apiRequest('/profile', { method: 'PUT', body: profile }),
  verifyProfile: () => apiRequest('/profile/verify', { method: 'POST' }),
  uploadResume: (file) => {
    const form = new FormData();
    form.append('file', file);
    return apiRequest('/profile/resume', { method: 'POST', body: form, isForm: true });
  },

  // Extraction
  extractOpportunities: (rawText) => apiRequest('/extract', { method: 'POST', body: { raw_text: rawText } }),

  // Campaign
  generateCampaign: (payload) => apiRequest('/campaign/generate', { method: 'POST', body: payload }),
  approveCampaign: (payload) => apiRequest('/campaign/approve', { method: 'POST', body: payload }),
  getCampaign: (threadId) => apiRequest(`/campaign/${encodeURIComponent(threadId)}`),
  listCampaigns: () => apiRequest('/campaign'),
};
