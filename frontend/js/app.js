/* ============================================================
   ColdMail AI Pro — App controller (vanilla JS, no build step)
   ============================================================ */

const PIPELINE_ORDER = ['research', 'match', 'personalize', 'write', 'review', 'approval', 'send'];

const State = {
  profile: null,          // last saved/loaded profile object
  opportunities: [],      // [{ id, company, email, role, job_description }]
  goal: 'full_time',
  currentThreadId: null,
  currentEmails: [],      // generated emails (with .index) for the active campaign
  approvedSet: new Set(),
  sentThreadIds: new Set(),
};

// ---------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------
function uid() { return Math.random().toString(36).slice(2, 10); }

function showLoading(text = 'Working…') {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading-overlay').hidden = false;
}
function hideLoading() {
  document.getElementById('loading-overlay').hidden = true;
}

function setBtnLoading(btn, isLoading) {
  btn.classList.toggle('is-loading', isLoading);
  btn.disabled = isLoading;
}

function scoreClass(score) {
  if (score >= 70) return '';
  if (score >= 45) return 'mid';
  return 'low';
}

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

// ---------------------------------------------------------------
// Pipeline tracker animation (visual feedback only — the backend
// call is a single blocking request, so this illustrates the
// known stage order of the LangGraph pipeline while we wait).
// ---------------------------------------------------------------
function makePipelineAnimator(containerEl) {
  let token = 0;
  const steps = PIPELINE_ORDER.map((name) => containerEl.querySelector(`[data-step="${name}"]`));

  function paint(activeIndex, doneUpTo) {
    steps.forEach((el, idx) => {
      if (!el) return;
      el.classList.toggle('done', idx <= doneUpTo);
      el.classList.toggle('active', idx === activeIndex);
    });
  }

  function reset() {
    token++;
    steps.forEach((el) => el && el.classList.remove('active', 'done'));
  }

  function runTo(holdIndex, msPerStep = 480) {
    const myToken = ++token;
    let i = 0;
    function tick() {
      if (myToken !== token) return;
      paint(i, i - 1);
      if (i >= holdIndex) return;
      i++;
      setTimeout(tick, msPerStep);
    }
    tick();
  }

  function finishAll() {
    token++;
    paint(-1, steps.length - 1);
  }

  return { reset, runTo, finishAll };
}

const campaignPipeline = makePipelineAnimator(document.getElementById('pipeline-tracker'));

// ---------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------
function navigateTo(viewName) {
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${viewName}`));
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.view === viewName));
  closeMobileSidebar();

  if (viewName === 'dashboard') renderDashboard();
  if (viewName === 'analytics') renderAnalytics();
  if (viewName === 'settings') loadSettingsForm();
  if (viewName === 'review') renderReview();
}

function wireNav() {
  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => navigateTo(btn.dataset.view));
  });
  document.querySelectorAll('[data-nav]').forEach((btn) => {
    btn.addEventListener('click', () => navigateTo(btn.dataset.nav));
  });
}

function closeMobileSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarScrim').classList.remove('show');
}

function wireMobileMenu() {
  const btn = document.getElementById('mobileMenuBtn');
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('sidebarScrim');
  btn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    scrim.classList.toggle('show');
  });
  scrim.addEventListener('click', closeMobileSidebar);
}

// ---------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------
async function renderDashboard() {
  const nameSuffix = document.getElementById('dash-name-suffix');
  nameSuffix.textContent = State.profile && State.profile.name ? `, ${State.profile.name.trim().split(' ')[0]}` : '';

  let data;
  try {
    data = await Api.listCampaigns();
  } catch (e) {
    toast('error', 'Could not load dashboard', e.message);
    return;
  }

  document.querySelectorAll('#dash-stats [data-stat]').forEach((el) => {
    const key = el.dataset.stat;
    const val = data.summary[key];
    el.firstChild ? (el.childNodes[0].textContent = key === 'avg_personalization' ? val : val) : null;
    if (key === 'avg_personalization') {
      el.innerHTML = `${val}<small>/100</small>`;
    } else {
      el.textContent = val;
    }
  });

  const listEl = document.getElementById('dash-campaign-list');
  if (!data.campaigns.length) {
    listEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M3 8l9 6 9-6M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1z"/></svg></div>
        <p>No campaigns yet.</p>
        <button class="btn btn-secondary" data-nav="campaign">Create your first campaign</button>
      </div>`;
    listEl.querySelector('[data-nav]').addEventListener('click', () => navigateTo('campaign'));
    return;
  }

  listEl.innerHTML = '';
  data.campaigns.slice(0, 8).forEach((c) => {
    const row = document.createElement('div');
    row.className = 'campaign-row';
    row.innerHTML = `
      <div class="campaign-row-main">
        <span class="campaign-row-title">${escapeHtml(c.profile_name || 'Campaign')} · ${escapeHtml((c.goal || '').replace('_', ' '))}</span>
        <span class="campaign-row-sub">${c.total_emails} emails · ${escapeHtml((c.companies || []).slice(0, 3).join(', '))}${c.companies && c.companies.length > 3 ? '…' : ''} · ${fmtDate(c.created_at)}</span>
      </div>
      <div class="campaign-row-right">
        <span class="badge status-${c.status}">${c.status.replace('_', ' ')}</span>
        ${c.status === 'awaiting_approval' ? `<button class="btn btn-secondary btn-sm" data-open-thread="${c.thread_id}">Review</button>` : ''}
      </div>`;
    listEl.appendChild(row);
  });
  listEl.querySelectorAll('[data-open-thread]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await loadThreadIntoReview(btn.dataset.openThread);
      navigateTo('review');
    });
  });
}

// ---------------------------------------------------------------
// Campaign: paste → extract → preview → generate
// ---------------------------------------------------------------
function wireCampaignView() {
  const rawInput = document.getElementById('raw-text-input');
  const charCount = document.getElementById('char-count');
  rawInput.addEventListener('input', () => {
    charCount.textContent = `${rawInput.value.length.toLocaleString()} characters`;
  });

  document.getElementById('extract-btn').addEventListener('click', handleExtract);
  document.getElementById('add-opportunity-btn').addEventListener('click', () => {
    addOpportunity({ id: uid(), company: '', email: '', role: '', job_description: '' });
    renderOpportunityList();
  });
  document.getElementById('goal-select').addEventListener('change', (e) => { State.goal = e.target.value; });
  document.getElementById('generate-btn').addEventListener('click', handleGenerate);
}

async function handleExtract() {
  const rawInput = document.getElementById('raw-text-input');
  const text = rawInput.value.trim();
  if (!text) {
    toast('error', 'Nothing to extract', 'Paste some text first — recruiter emails, LinkedIn messages, job posts, anything.');
    return;
  }

  const btn = document.getElementById('extract-btn');
  setBtnLoading(btn, true);
  showLoading('Reading your text and finding opportunities…');

  try {
    const res = await Api.extractOpportunities(text);
    State.opportunities = res.opportunities.map((o) => ({ id: uid(), ...o }));
    renderOpportunityList();
    document.getElementById('extract-panel').hidden = true;
    document.getElementById('preview-panel').hidden = false;
    toast('success', `Found ${State.opportunities.length} opportunit${State.opportunities.length === 1 ? 'y' : 'ies'}`, 'Review and edit them below before generating emails.');
  } catch (e) {
    toast('error', 'Extraction failed', e.message);
  } finally {
    setBtnLoading(btn, false);
    hideLoading();
  }
}

function addOpportunity(opp) {
  State.opportunities.push(opp);
}

function removeOpportunity(id) {
  State.opportunities = State.opportunities.filter((o) => o.id !== id);
  renderOpportunityList();
}

function renderOpportunityList() {
  const container = document.getElementById('opportunity-list');
  container.innerHTML = '';

  State.opportunities.forEach((opp) => {
    const card = document.createElement('div');
    card.className = 'opp-card';
    card.dataset.oppId = opp.id;

    const isValidEmail = !!(opp.email && opp.email.includes('@'));
    card.classList.toggle('invalid', !isValidEmail);

    card.innerHTML = `
      <div class="opp-card-row">
        <div class="opp-field">
          <label>Company</label>
          <input type="text" data-field="company" value="${escapeAttr(opp.company)}" placeholder="Company or contact name">
        </div>
        <div class="opp-field">
          <label>Email <span class="opp-email-warning">— required to send</span></label>
          <input type="email" data-field="email" value="${escapeAttr(opp.email)}" placeholder="name@company.com">
        </div>
      </div>
      <div class="opp-card-row" style="grid-template-columns:1fr;">
        <div class="opp-field">
          <label>Role</label>
          <input type="text" data-field="role" value="${escapeAttr(opp.role)}" placeholder="e.g. Machine Learning Intern">
        </div>
      </div>
      <div class="opp-card-row" style="grid-template-columns:1fr;">
        <div class="opp-field">
          <label>Job Description / Context</label>
          <textarea data-field="job_description" placeholder="Paste or leave blank...">${escapeHtml(opp.job_description)}</textarea>
        </div>
      </div>
      <div class="opp-card-foot">
        <span></span>
        <button class="btn btn-danger-ghost btn-sm" data-remove>Remove</button>
      </div>
    `;

    card.querySelectorAll('[data-field]').forEach((input) => {
      input.addEventListener('input', () => {
        opp[input.dataset.field] = input.value;
        if (input.dataset.field === 'email') {
          card.classList.toggle('invalid', !(opp.email && opp.email.includes('@')));
        }
        updateOppCount();
      });
    });
    card.querySelector('[data-remove]').addEventListener('click', () => removeOpportunity(opp.id));

    container.appendChild(card);
  });

  updateOppCount();
}

function updateOppCount() {
  const valid = State.opportunities.filter((o) => o.email && o.email.includes('@')).length;
  document.getElementById('opp-count').textContent =
    `${valid} of ${State.opportunities.length} opportunit${State.opportunities.length === 1 ? 'y' : 'ies'} ready`;
  document.getElementById('generate-btn').disabled = valid === 0;
}

function profileIsComplete(p) {
  return !!(p && p.name && p.email && p.college && p.degree && p.graduation_year && p.objective);
}

async function handleGenerate() {
  const validOpps = State.opportunities.filter((o) => o.email && o.email.includes('@'));
  if (!validOpps.length) {
    toast('error', 'No valid opportunities', 'At least one opportunity needs a valid email address.');
    return;
  }
  if (!profileIsComplete(State.profile)) {
    toast('error', 'Complete your profile first', 'Add your name, email, college, degree and objective in Profile & Settings.');
    navigateTo('settings');
    return;
  }

  const btn = document.getElementById('generate-btn');
  setBtnLoading(btn, true);
  showLoading('Agents at work: researching, matching, and writing…');
  campaignPipeline.reset();
  campaignPipeline.runTo(5); // animate through to "Human Approval"

  try {
    const payload = {
      profile: buildProfilePayload(State.profile),
      goal: State.goal,
      opportunities: validOpps.map(({ company, email, role, job_description }) => ({ company, email, role, job_description })),
    };
    const res = await Api.generateCampaign(payload);
    campaignPipeline.finishAll();

    State.currentThreadId = res.thread_id;
    State.currentEmails = res.emails;
    State.approvedSet = new Set();
    State.sentThreadIds.delete(res.thread_id);

    if (res.errors && res.errors.length) {
      toast('info', 'Generated with some warnings', res.errors.join('; '));
    }
    toast('success', `${res.emails.length} email${res.emails.length === 1 ? '' : 's'} generated`, 'Review and approve them to send.');

    // reset campaign view for next time
    document.getElementById('raw-text-input').value = '';
    document.getElementById('char-count').textContent = '0 characters';
    document.getElementById('extract-panel').hidden = false;
    document.getElementById('preview-panel').hidden = true;
    State.opportunities = [];

    navigateTo('review');
  } catch (e) {
    campaignPipeline.reset();
    toast('error', 'Generation failed', e.message);
  } finally {
    setBtnLoading(btn, false);
    hideLoading();
  }
}

function buildProfilePayload(p) {
  return {
    name: p.name,
    email: p.email,
    phone: p.phone || null,
    linkedin: p.linkedin || null,
    github: p.github || null,
    portfolio: p.portfolio || null,
    resume_path: p.resume_path || null,
    college: p.college,
    degree: p.degree,
    graduation_year: Number(p.graduation_year),
    skills: Array.isArray(p.skills) ? p.skills : String(p.skills || '').split(',').map((s) => s.trim()).filter(Boolean),
    objective: p.objective,
    tone: p.tone || 'professional',
  };
}

// ---------------------------------------------------------------
// Review & Send
// ---------------------------------------------------------------
async function loadThreadIntoReview(threadId) {
  showLoading('Loading campaign…');
  try {
    const data = await Api.getCampaign(threadId);
    State.currentThreadId = threadId;
    State.currentEmails = data.emails;
    State.approvedSet = new Set();
    if (!data.awaiting_approval) State.sentThreadIds.add(threadId);
  } catch (e) {
    toast('error', 'Could not load campaign', e.message);
  } finally {
    hideLoading();
  }
}

function updateReviewBadge() {
  const badge = document.getElementById('review-badge');
  const pending = State.currentThreadId && !State.sentThreadIds.has(State.currentThreadId) ? State.currentEmails.length : 0;
  badge.hidden = pending === 0;
  badge.textContent = pending;
}

function renderReview() {
  const emptyEl = document.getElementById('review-empty');
  const contentEl = document.getElementById('review-content');
  const summaryEl = document.getElementById('send-summary');
  summaryEl.hidden = true;

  if (!State.currentThreadId || !State.currentEmails.length) {
    emptyEl.hidden = false;
    contentEl.hidden = true;
    updateReviewBadge();
    return;
  }

  if (State.sentThreadIds.has(State.currentThreadId)) {
    // already sent — nothing to review, content stays hidden
    emptyEl.hidden = true;
    contentEl.hidden = true;
    updateReviewBadge();
    return;
  }

  emptyEl.hidden = true;
  contentEl.hidden = false;

  const listEl = document.getElementById('email-review-list');
  listEl.innerHTML = '';

  State.currentEmails.forEach((email) => {
    listEl.appendChild(buildEmailCard(email));
  });

  updateSendButtonLabel();
  updateReviewBadge();
}

function buildEmailCard(email) {
  const idx = email.index;
  const card = document.createElement('div');
  card.className = 'email-card';
  card.dataset.index = idx;

  const score = email.personalization_score || 0;

  card.innerHTML = `
    <div class="email-card-top">
      <div class="email-meta">
        <span class="email-company">${escapeHtml(email.company_name || 'Contact')}</span>
        <span class="email-recipient">${escapeHtml(email.recipient_email)}</span>
      </div>
      <div class="email-card-right">
        <span class="score-badge ${scoreClass(score)}">★ ${score}/100</span>
        <label class="toggle-approve">
          Approve
          <input type="checkbox" data-approve>
          <span class="toggle-switch"></span>
        </label>
      </div>
    </div>
    <div class="email-fields">
      <div class="field">
        <label>Role / Position</label>
        <input type="text" data-field="role" value="${escapeAttr(email.role || '')}">
      </div>
      <div class="field">
        <label>Subject</label>
        <input type="text" data-field="subject" value="${escapeAttr(email.subject || '')}">
      </div>
    </div>
    <div class="email-preview" data-email-preview>${escapeHtml(email.body || '')}</div>
    <div class="email-meta-strip"><span data-word-count>${countWords(email.body || '')} words</span><span>${email.resume_attached !== false ? 'Resume attached' : 'No resume attached'}</span>${linkCount(email.body) ? `<span class="link-chip">${linkCount(email.body)} profile link${linkCount(email.body) === 1 ? '' : 's'} included</span>` : '<span class="warning-chip">Add profile links in Settings</span>'}</div>
    ${email.key_points_used && email.key_points_used.length ? `<div class="key-points"><strong>Personalization:</strong> ${escapeHtml(email.key_points_used.join(', '))}</div>` : ''}
    ${email.match ? `<div class="key-points"><strong>Match:</strong> ${email.match.overall_score}/100 · Required skills ${Math.round(email.match.required_skill_match || 0)}% · Semantic ${Math.round(email.match.semantic_match || 0)}%</div>` : ''}
    ${email.review ? `<div class="key-points"><strong>AI Review:</strong> ${email.review.overall_score}/10 · Grounding ${email.review.evidence_grounding_score}/10${email.review.needs_rewrite ? ' · Rewrite recommended' : ''}</div>` : ''}
    ${email.evidence && email.evidence.length ? `<div class="key-points"><strong>Evidence:</strong> ${email.evidence.slice(0,3).map(e => `[${escapeHtml(e.id)}] ${escapeHtml(e.claim)}`).join(' · ')}</div>` : ''}
    <button class="email-body-toggle" data-toggle-body>
      <svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
      View / edit full email
    </button>
    <div class="email-body-wrap">
      <textarea class="email-body-textarea" data-field="body">${escapeHtml(email.body || '')}</textarea>
    </div>
  `;

  // Field edits update State.currentEmails directly
  card.querySelectorAll('[data-field]').forEach((input) => {
    input.addEventListener('input', () => {
      email[input.dataset.field] = input.value;
      if (input.dataset.field === 'body') {
        const preview = card.querySelector('[data-email-preview]');
        const words = card.querySelector('[data-word-count]');
        if (preview) preview.textContent = input.value;
        if (words) words.textContent = `${countWords(input.value)} words`;
      }
      if (input.dataset.field === 'subject' || input.dataset.field === 'role') {
        // keep header in sync visually is optional; nothing else needed
      }
    });
  });

  card.querySelector('[data-approve]').addEventListener('change', (e) => {
    if (e.target.checked) State.approvedSet.add(idx);
    else State.approvedSet.delete(idx);
    card.classList.toggle('approved', e.target.checked);
    updateSendButtonLabel();
  });

  const toggleBtn = card.querySelector('[data-toggle-body]');
  const bodyWrap = card.querySelector('.email-body-wrap');
  toggleBtn.addEventListener('click', () => {
    const open = bodyWrap.classList.toggle('open');
    toggleBtn.classList.toggle('open', open);
  });

  return card;
}

function updateSendButtonLabel() {
  const n = State.approvedSet.size;
  document.getElementById('send-approved-label').textContent = n > 0 ? `Send ${n} Approved Email${n === 1 ? '' : 's'}` : 'Send Approved Emails';
  document.getElementById('send-approved-btn').disabled = n === 0;
}

function wireReviewView() {
  document.getElementById('approve-all-btn').addEventListener('click', () => {
    State.currentEmails.forEach((e) => State.approvedSet.add(e.index));
    document.querySelectorAll('#email-review-list .email-card').forEach((card) => {
      card.classList.add('approved');
      card.querySelector('[data-approve]').checked = true;
    });
    updateSendButtonLabel();
  });

  document.getElementById('clear-approval-btn').addEventListener('click', () => {
    State.approvedSet.clear();
    document.querySelectorAll('#email-review-list .email-card').forEach((card) => {
      card.classList.remove('approved');
      card.querySelector('[data-approve]').checked = false;
    });
    updateSendButtonLabel();
  });

  document.getElementById('send-approved-btn').addEventListener('click', handleSendApproved);
  document.getElementById('new-campaign-after-send').addEventListener('click', () => {
    document.getElementById('send-summary').hidden = true;
    navigateTo('campaign');
  });
}

async function handleSendApproved() {
  if (!State.approvedSet.size) return;

  const btn = document.getElementById('send-approved-btn');
  setBtnLoading(btn, true);
  showLoading('Sending approved emails…');
  campaignPipeline.runTo(6);

  const editedEmails = State.currentEmails.map((e) => ({
    index: e.index,
    role: e.role || null,
    subject: e.subject || null,
    body: e.body || null,
  }));

  try {
    const res = await Api.approveCampaign({
      thread_id: State.currentThreadId,
      approved_indices: Array.from(State.approvedSet),
      edited_emails: editedEmails,
    });
    campaignPipeline.finishAll();
    State.sentThreadIds.add(State.currentThreadId);

    document.getElementById('review-content').hidden = true;
    const summaryEl = document.getElementById('send-summary');
    summaryEl.hidden = false;
    document.getElementById('summary-sent').textContent = res.sent;
    document.getElementById('summary-failed').textContent = res.failed;

    const detailsEl = document.getElementById('send-details');
    detailsEl.innerHTML = '';
    (res.details || []).forEach((d) => {
      const row = document.createElement('div');
      row.className = 'send-detail-row';
      const status = d.success ? (d.demo ? 'demo' : 'ok') : 'fail';
      const label = d.success ? (d.demo ? 'Demo mode' : 'Sent') : 'Failed';
      row.innerHTML = `<span>${escapeHtml(d.recipient || '')}</span><span class="sd-status ${status}">${label}</span>${d.error ? `<div class="sd-error">${escapeHtml(d.error)}</div>` : ''}`;
      detailsEl.appendChild(row);
    });

    toast('success', `Sent ${res.sent} email${res.sent === 1 ? '' : 's'}`, res.failed ? `${res.failed} failed to send.` : 'Campaign complete.');
    updateReviewBadge();
  } catch (e) {
    campaignPipeline.reset();
    toast('error', 'Sending failed', e.message);
  } finally {
    setBtnLoading(btn, false);
    hideLoading();
  }
}

// ---------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------
async function renderAnalytics() {
  let data;
  try {
    data = await Api.listCampaigns();
  } catch (e) {
    toast('error', 'Could not load analytics', e.message);
    return;
  }

  document.querySelectorAll('#analytics-stats [data-astat]').forEach((el) => {
    const key = el.dataset.astat;
    const val = data.summary[key];
    el.innerHTML = key === 'avg_personalization' ? `${val}<small>/100</small>` : val;
  });

  const breakdownEl = document.getElementById('analytics-breakdown');
  if (!data.campaigns.length) {
    breakdownEl.innerHTML = `<div class="empty-state"><p>No campaign data yet — run a campaign to see analytics here.</p></div>`;
    return;
  }

  breakdownEl.innerHTML = '';
  data.campaigns.forEach((c) => {
    const total = Math.max(c.total_emails, 1);
    const sentPct = (c.sent / total) * 100;
    const failedPct = (c.failed / total) * 100;
    const row = document.createElement('div');
    row.className = 'ab-row';
    row.innerHTML = `
      <div class="ab-row-top">
        <span class="ab-row-title">${escapeHtml(c.profile_name || 'Campaign')} · ${escapeHtml((c.goal || '').replace('_', ' '))}</span>
        <span class="ab-row-meta">${c.sent} sent / ${c.failed} failed / ${c.total_emails} total · avg ${c.avg_personalization || 0}/100 · ${fmtDate(c.created_at)}</span>
      </div>
      <div class="ab-bar">
        <div class="ab-bar-sent" style="width:${sentPct}%"></div>
        <div class="ab-bar-failed" style="width:${failedPct}%"></div>
      </div>
    `;
    breakdownEl.appendChild(row);
  });
}

// ---------------------------------------------------------------
// Profile & Settings
// ---------------------------------------------------------------
function loadSettingsForm() {
  const form = document.getElementById('profile-form');
  const p = State.profile || {};
  form.name.value = p.name || '';
  form.email.value = p.email || '';
  form.phone.value = p.phone || '';
  form.linkedin.value = p.linkedin || '';
  form.github.value = p.github || '';
  form.portfolio.value = p.portfolio || '';
  form.leetcode.value = p.leetcode || '';
  form.college.value = p.college || '';
  form.degree.value = p.degree || '';
  form.graduation_year.value = p.graduation_year || '';
  form.skills.value = Array.isArray(p.skills) ? p.skills.join(', ') : (p.skills || '');
  form.objective.value = p.objective || '';
  form.tone.value = p.tone || 'confident';

  document.getElementById('resume-filename').textContent = p.resume_path ? `Attached: ${p.resume_path.split('/').pop()}` : '';
}

function wireSettingsView() {
  const dropzone = document.getElementById('resume-dropzone');
  const fileInput = document.getElementById('resume-file-input');

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleResumeUpload(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleResumeUpload(fileInput.files[0]);
  });

  document.getElementById('save-profile-btn').addEventListener('click', handleSaveProfile);
}

async function handleResumeUpload(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    toast('error', 'PDF only', 'Please upload your resume as a PDF file.');
    return;
  }
  showLoading('Uploading and parsing resume…');
  try {
    const res = await Api.uploadResume(file);
    State.profile = State.profile || {};
    State.profile.resume_path = res.resume_path;
    document.getElementById('resume-filename').textContent = `Attached: ${file.name}`;

    const form = document.getElementById('profile-form');
    const parsed = res.parsed || {};
    let filled = 0;
    if (parsed.name && !form.name.value) { form.name.value = parsed.name; filled++; }
    if (parsed.email && !form.email.value) { form.email.value = parsed.email; filled++; }
    if (parsed.phone && !form.phone.value) { form.phone.value = parsed.phone; filled++; }
    if (parsed.linkedin && !form.linkedin.value) { form.linkedin.value = parsed.linkedin; filled++; }
    if (parsed.github && !form.github.value) { form.github.value = parsed.github; filled++; }
    if (parsed.portfolio && !form.portfolio.value) { form.portfolio.value = parsed.portfolio; filled++; }
    if (parsed.leetcode && !form.leetcode.value) { form.leetcode.value = parsed.leetcode; filled++; }
    if (parsed.skills && parsed.skills.length && !form.skills.value) { form.skills.value = parsed.skills.join(', '); filled++; }

    toast('success', 'Resume attached', filled ? `Prefilled ${filled} field${filled === 1 ? '' : 's'} from your resume — review and save.` : 'It will be attached to outgoing emails.');
  } catch (e) {
    toast('error', 'Resume upload failed', e.message);
  } finally {
    hideLoading();
  }
}

async function handleSaveProfile() {
  const form = document.getElementById('profile-form');
  if (!form.reportValidity()) return;

  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    phone: form.phone.value.trim() || null,
    linkedin: form.linkedin.value.trim() || null,
    github: form.github.value.trim() || null,
    portfolio: form.portfolio.value.trim() || null,
    leetcode: form.leetcode.value.trim() || null,
    resume_path: (State.profile && State.profile.resume_path) || null,
    college: form.college.value.trim(),
    degree: form.degree.value.trim(),
    graduation_year: Number(form.graduation_year.value),
    skills: form.skills.value.split(',').map((s) => s.trim()).filter(Boolean),
    objective: form.objective.value.trim(),
    tone: form.tone.value,
  };

  const btn = document.getElementById('save-profile-btn');
  setBtnLoading(btn, true);
  try {
    const res = await Api.saveProfile(payload);
    State.profile = res.profile;
    const status = document.getElementById('profile-save-status');
    status.textContent = 'Saved ✓';
    status.classList.add('show');
    setTimeout(() => status.classList.remove('show'), 2500);

    if (!res.profile.profile_verified) {
      toast('success', 'Profile saved', 'Review it once more, then confirm to continue.');
      renderVerifyScreen(res.profile);
      showScreen('verify');
    } else {
      renderSidebarUser(res.profile);
      toast('success', 'Profile saved', 'This will be used to personalize your emails.');
    }
  } catch (e) {
    toast('error', 'Could not save profile', e.message);
  } finally {
    setBtnLoading(btn, false);
  }
}

function countWords(str) {
  return (String(str || '').match(/\b[\w’'-]+\b/g) || []).length;
}

function linkCount(str) {
  return (String(str || '').match(/https?:\/\/[^\s<>]+/gi) || []).length;
}

// ---------------------------------------------------------------
// Escaping helpers
// ---------------------------------------------------------------
function escapeAttr(str) {
  return escapeHtml(str).replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------
// Auth / profile-verification state machine
//
// Exactly one of #auth-screen, #verify-screen, #app-shell is visible at any
// time (enforced by the `[hidden]` -> display:none !important rule in
// styles.css), so the login screen and the dashboard can never overlap.
// ---------------------------------------------------------------
function showScreen(name) {
  const screens = { auth: 'auth-screen', verify: 'verify-screen', app: 'app-shell' };
  Object.entries(screens).forEach(([key, id]) => {
    document.getElementById(id).hidden = key !== name;
  });
}

function onSessionExpired() {
  State.profile = null;
  showScreen('auth');
  toast('error', 'Session expired', 'Please log in again.');
}

function setAuthError(formName, message) {
  const el = document.getElementById(`${formName}-error`);
  if (!message) { el.hidden = true; el.textContent = ''; return; }
  el.textContent = message;
  el.hidden = false;
}

function wireAuthScreen() {
  document.querySelectorAll('.auth-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.auth-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      const isLogin = tab.dataset.authTab === 'login';
      document.getElementById('login-form').hidden = !isLogin;
      document.getElementById('signup-form').hidden = isLogin;
      setAuthError('login', null);
      setAuthError('signup', null);
    });
  });

  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    setAuthError('login', null);
    const form = e.target;
    const btn = document.getElementById('login-submit');
    setBtnLoading(btn, true);
    try {
      const res = await Api.login({ email: form.email.value.trim(), password: form.password.value });
      Auth.setToken(res.access_token);
      await handleAuthenticated(res.user);
    } catch (err) {
      setAuthError('login', err.message || 'Could not log in.');
    } finally {
      setBtnLoading(btn, false);
    }
  });

  document.getElementById('signup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    setAuthError('signup', null);
    const form = e.target;
    const btn = document.getElementById('signup-submit');
    setBtnLoading(btn, true);
    try {
      const res = await Api.signup({
        name: form.name.value.trim(),
        email: form.email.value.trim(),
        password: form.password.value,
      });
      Auth.setToken(res.access_token);
      await handleAuthenticated(res.user);
    } catch (err) {
      setAuthError('signup', err.message || 'Could not create account.');
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts[0][0] + (parts[1] ? parts[1][0] : '')).toUpperCase();
}

function renderSidebarUser(profile) {
  document.getElementById('sidebar-user-avatar').textContent = initials(profile.name);
  document.getElementById('sidebar-user-name').textContent = profile.name || 'Your account';
  document.getElementById('sidebar-user-email').textContent = profile.email || '';
}

function wireLogout() {
  document.getElementById('logout-btn').addEventListener('click', async () => {
    try { await Api.logout(); } catch { /* stateless token; ignore network errors */ }
    Auth.clear();
    State.profile = null;
    document.getElementById('login-form').reset();
    showScreen('auth');
  });
}

// ---------------------------------------------------------------
// Profile verification screen
// ---------------------------------------------------------------
function verifyRow(label, value, opts = {}) {
  const empty = value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length);
  const display = empty ? 'Not added yet' : (Array.isArray(value) ? value.join(', ') : value);
  const cls = ['verify-row-value'];
  if (empty) cls.push('muted');
  if (opts.link && !empty) cls.push('link');
  return `
    <div class="verify-row${opts.wide ? ' wide' : ''}">
      <span class="verify-row-label">${escapeHtml(label)}</span>
      <span class="${cls.join(' ')}">${escapeHtml(String(display))}</span>
    </div>`;
}

function renderVerifyScreen(profile) {
  const pct = profile.profile_completeness || 0;
  document.getElementById('verify-progress-fill').style.width = `${pct}%`;
  document.getElementById('verify-progress-label').textContent = `Profile completeness — ${pct}%`;

  const summary = document.getElementById('verify-summary');
  summary.innerHTML = [
    verifyRow('Name', profile.name),
    verifyRow('Email', profile.email),
    verifyRow('Phone', profile.phone),
    verifyRow('College / Degree', [profile.college, profile.degree].filter(Boolean).join(' — ')),
    verifyRow('LinkedIn', profile.linkedin, { link: true }),
    verifyRow('GitHub', profile.github, { link: true }),
    verifyRow('Portfolio', profile.portfolio, { link: true }),
    verifyRow('Skills', profile.skills, { wide: true }),
    verifyRow('Resume', profile.resume_filename || (profile.resume_path ? 'Attached' : null)),
    verifyRow('Career Objective', profile.objective, { wide: true }),
  ].join('');
}

function wireVerifyScreen() {
  document.getElementById('verify-edit-btn').addEventListener('click', () => {
    showScreen('app');
    navigateTo('settings');
    toast('info', 'Editing profile', 'Save your changes, then confirm to continue to the dashboard.');
  });

  document.getElementById('verify-confirm-btn').addEventListener('click', async () => {
    const btn = document.getElementById('verify-confirm-btn');
    setBtnLoading(btn, true);
    document.getElementById('verify-error').hidden = true;
    try {
      const res = await Api.verifyProfile();
      State.profile = res.profile;
      enterApp();
    } catch (err) {
      const el = document.getElementById('verify-error');
      el.textContent = err.message || 'Could not confirm profile.';
      el.hidden = false;
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

// ---------------------------------------------------------------
// Transition into the authenticated app shell
// ---------------------------------------------------------------
function enterApp() {
  renderSidebarUser(State.profile);
  showScreen('app');
  navigateTo('dashboard');
}

async function handleAuthenticated(profile) {
  State.profile = profile;
  if (profile.profile_verified) {
    enterApp();
  } else {
    renderVerifyScreen(profile);
    showScreen('verify');
  }
}

// ---------------------------------------------------------------
// Init
// ---------------------------------------------------------------
async function init() {
  // App-shell interactions are wired up-front (harmless while hidden);
  // only entry into the shell itself is gated behind auth + verification.
  wireNav();
  wireMobileMenu();
  wireCampaignView();
  wireReviewView();
  wireSettingsView();
  wireAuthScreen();
  wireVerifyScreen();
  wireLogout();

  if (!Auth.getToken()) {
    showScreen('auth');
    return;
  }

  try {
    const profile = await Api.me();
    await handleAuthenticated(profile);
  } catch {
    Auth.clear();
    showScreen('auth');
  }
}

document.addEventListener('DOMContentLoaded', init);
