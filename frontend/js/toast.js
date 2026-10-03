/* ============================================================
   Toast notifications
   ============================================================ */
const TOAST_ICONS = {
  success: '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>',
  error: '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>',
  info: '<svg viewBox="0 0 24 24"><path d="M12 16v-4M12 8h.01"/><circle cx="12" cy="12" r="9"/></svg>',
};

function toast(type, title, message = '', duration = 4800) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    <div class="toast-icon">${TOAST_ICONS[type] || TOAST_ICONS.info}</div>
    <div class="toast-body">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${message ? `<div class="toast-msg">${escapeHtml(message)}</div>` : ''}
    </div>
    <button class="toast-close" aria-label="Dismiss">
      <svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
    </button>
  `;

  const remove = () => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 200);
  };

  el.querySelector('.toast-close').addEventListener('click', remove);
  container.appendChild(el);

  if (duration > 0) setTimeout(remove, duration);
  return el;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}
