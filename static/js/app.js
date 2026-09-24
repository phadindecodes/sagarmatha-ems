/**
 * app.js - Core State, Router, RBAC & Authentication Handlers
 * Shree Sagarmatha Secondary School & Sagarmatha EMS
 */

const State = {
  activeView: 'public',
  schoolInfo: null,
  classes: [],
  activeClass: null,
  activeExam: null,
  currentUser: null,
  authToken: localStorage.getItem('sagarmatha_token') || null
};

// Global Fetch Interceptor for Automatic Bearer Auth
const _nativeFetch = window.fetch;
window.fetch = function(url, options = {}) {
  options = options || {};
  if (State.authToken) {
    if (!options.headers) options.headers = {};
    if (options.headers instanceof Headers) {
      options.headers.set('Authorization', `Bearer ${State.authToken}`);
    } else {
      options.headers['Authorization'] = `Bearer ${State.authToken}`;
    }
  }
  return _nativeFetch(url, options).then(res => {
    if (res.status === 401 && String(url).startsWith('/api/') && !String(url).includes('/api/auth/login')) {
      if (State.currentUser) {
        showToast('Session expired or login required.', 'error');
      }
      logoutUser(false);
      openModal('login-modal');
    }
    return res;
  });
};

function apiFetch(url, options = {}) {
  options = options || {};
  if (!options.headers) options.headers = {};
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    if (!options.headers['Content-Type']) {
      options.headers['Content-Type'] = 'application/json';
    }
    options.body = JSON.stringify(options.body);
  }
  return window.fetch(url, options);
}
window.apiFetch = apiFetch;

// UI Helpers
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠'}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('open');
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('open');
  }
}

// Authentication & Session Management
async function checkAuthStatus() {
  if (!State.authToken) {
    updateAuthUI(null);
    return false;
  }

  try {
    const res = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${State.authToken}` }
    });
    const data = await res.json();
    if (data.authenticated && data.user) {
      State.currentUser = data.user;
      updateAuthUI(data.user);
      return true;
    } else {
      logoutUser(false);
      return false;
    }
  } catch (err) {
    logoutUser(false);
    return false;
  }
}

async function loginUser(username, password) {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();

    if (data.success && data.token) {
      State.authToken = data.token;
      State.currentUser = data.user;
      localStorage.setItem('sagarmatha_token', data.token);

      updateAuthUI(data.user);
      closeModal('login-modal');
      showToast(`Welcome, ${data.user.full_name}! (${data.user.role.toUpperCase()})`, 'success');

      // Navigate to default view for role
      if (data.user.role === 'student') {
        switchView('studentportal');
      } else {
        switchView('dashboard');
      }
      return true;
    } else {
      const errorElem = document.getElementById('login-error-msg');
      if (errorElem) {
        errorElem.textContent = data.error || 'Invalid credentials';
        errorElem.style.display = 'block';
      }
      return false;
    }
  } catch (err) {
    showToast('Network error during login', 'error');
    return false;
  }
}

function logoutUser(redirectPublic = true) {
  if (State.authToken) {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${State.authToken}` }
    }).catch(() => {});
  }

  State.authToken = null;
  State.currentUser = null;
  localStorage.removeItem('sagarmatha_token');
  updateAuthUI(null);

  if (redirectPublic) {
    showToast('Logged out successfully', 'success');
    switchView('public');
  }
}

function fillDemoLogin(role) {
  const form = document.getElementById('login-form');
  if (!form) return;

  if (role === 'admin') {
    form.username.value = 'admin';
    form.password.value = 'admin123';
  } else if (role === 'teacher') {
    form.username.value = 'teacher';
    form.password.value = 'teacher123';
  } else if (role === 'accountant') {
    form.username.value = 'accountant';
    form.password.value = 'account123';
  } else if (role === 'student') {
    form.username.value = 'student10';
    form.password.value = 'student123';
  }
}

function updateAuthUI(user) {
  const userIndicator = document.getElementById('ems-user-indicator');
  const roleBadge = document.getElementById('ems-user-role-badge');
  const userName = document.getElementById('ems-user-name');
  const loginTriggerBtn = document.getElementById('public-login-trigger-btn');
  const topbarAuthBtn = document.getElementById('topbar-auth-btn');

  if (user) {
    if (userIndicator) userIndicator.style.display = 'flex';
    if (userName) userName.textContent = user.full_name;
    if (roleBadge) {
      roleBadge.textContent = user.role.toUpperCase();
      roleBadge.className = `badge ${
        user.role === 'admin' ? 'badge-danger' : 
        user.role === 'teacher' ? 'badge-info' : 
        user.role === 'accountant' ? 'badge-warning' : 'badge-success'
      }`;
    }
    if (loginTriggerBtn) loginTriggerBtn.textContent = `💻 Sagarmatha EMS (${user.role.toUpperCase()})`;
    if (topbarAuthBtn) topbarAuthBtn.textContent = `Portal (${user.role.toUpperCase()})`;

    applyRolePermissionsUI(user.role);
  } else {
    if (userIndicator) userIndicator.style.display = 'none';
    if (loginTriggerBtn) loginTriggerBtn.textContent = '🚀 Sagarmatha EMS Login';
    if (topbarAuthBtn) topbarAuthBtn.textContent = '🔐 Sagarmatha EMS Portal';
  }
}

// Role Hierarchy UI Adjustments
function applyRolePermissionsUI(role) {
  // Sidebar items
  const menuItems = {
    dashboard: document.querySelector('.sidebar-item[data-view="dashboard"]'),
    students: document.querySelector('.sidebar-item[data-view="students"]'),
    exam: document.querySelector('.sidebar-item[data-view="exam"]'),
    finance: document.querySelector('.sidebar-item[data-view="finance"]'),
    attendance: document.querySelector('.sidebar-item[data-view="attendance"]'),
    staff: document.querySelector('.sidebar-item[data-view="staff"]'),
    notices: document.querySelector('.sidebar-item[data-view="notices"]'),
    inquiries: document.querySelector('.sidebar-item[data-view="inquiries"]'),
    studentportal: document.querySelector('.sidebar-item[data-view="studentportal"]')
  };

  // Reset display
  Object.values(menuItems).forEach(el => { if (el) el.style.display = 'flex'; });

  if (role === 'admin') {
    if (menuItems.studentportal) menuItems.studentportal.style.display = 'none';
  } else if (role === 'teacher') {
    if (menuItems.finance) menuItems.finance.style.display = 'none';
    if (menuItems.staff) menuItems.staff.style.display = 'none';
    if (menuItems.studentportal) menuItems.studentportal.style.display = 'none';
  } else if (role === 'accountant') {
    if (menuItems.exam) menuItems.exam.style.display = 'none';
    if (menuItems.attendance) menuItems.attendance.style.display = 'none';
    if (menuItems.inquiries) menuItems.inquiries.style.display = 'none';
    if (menuItems.studentportal) menuItems.studentportal.style.display = 'none';
  } else if (role === 'student') {
    // For student, hide administrative tools, show Student Portal
    ['dashboard', 'students', 'exam', 'finance', 'attendance', 'staff', 'inquiries'].forEach(k => {
      if (menuItems[k]) menuItems[k].style.display = 'none';
    });
    if (menuItems.studentportal) menuItems.studentportal.style.display = 'flex';
  }
}

// Router
function switchView(viewName, subParam = null) {
  // Access Protection Guard
  if (viewName !== 'public' && !State.currentUser) {
    openModal('login-modal');
    return;
  }

  State.activeView = viewName;

  const publicWebsite = document.getElementById('public-website-view');
  const emsPortal = document.getElementById('ems-portal-view');
  const navPublic = document.querySelector('.navbar-public');

  if (viewName === 'public') {
    if (publicWebsite) publicWebsite.style.display = 'block';
    if (emsPortal) emsPortal.style.display = 'none';
    if (navPublic) navPublic.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    if (publicWebsite) publicWebsite.style.display = 'none';
    if (emsPortal) emsPortal.style.display = 'grid';
    if (navPublic) navPublic.style.display = 'none';

    // Update active sidebar item
    document.querySelectorAll('.sidebar-item').forEach(el => {
      if (el.dataset.view === viewName) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });

    // Hide all EMS sub-views
    document.querySelectorAll('.ems-view-panel').forEach(panel => {
      panel.style.display = 'none';
    });

    // Show selected panel
    const targetPanel = document.getElementById(`ems-${viewName}-panel`);
    if (targetPanel) {
      targetPanel.style.display = 'block';
    }

    // Trigger view-specific loads
    if (viewName === 'dashboard') loadDashboardData();
    if (viewName === 'students') loadStudentsView();
    if (viewName === 'exam') loadExamView(subParam);
    if (viewName === 'finance') loadFinanceView();
    if (viewName === 'staff') loadStaffView();
    if (viewName === 'attendance') loadAttendanceView();
    if (viewName === 'notices') loadNoticesEMS();
    if (viewName === 'inquiries') loadInquiriesEMS();
    if (viewName === 'studentportal') loadStudentPortalView();
  }
}

// Global Data Fetchers
async function fetchSchoolInfo() {
  try {
    const res = await fetch('/api/info');
    const data = await res.json();
    State.schoolInfo = data;
    renderSchoolInfo(data);
  } catch (err) {
    console.error('Failed to load school info:', err);
  }
}

async function fetchClasses() {
  try {
    const res = await fetch('/api/classes');
    const data = await res.json();
    State.classes = data;
    populateClassDropdowns(data);
    if (typeof populateExamClassDropdowns === 'function') {
      populateExamClassDropdowns();
    }
  } catch (err) {
    console.error('Failed to load classes:', err);
  }
}

function renderSchoolInfo(info) {
  document.querySelectorAll('.school-name-en').forEach(el => el.textContent = info.name_en);
  document.querySelectorAll('.school-name-np').forEach(el => el.textContent = info.name_np);
  document.querySelectorAll('.school-address-en').forEach(el => el.textContent = info.address_en);
  document.querySelectorAll('.school-address-np').forEach(el => el.textContent = info.address_np);
  document.querySelectorAll('.school-estd').forEach(el => el.textContent = `Estd. ${info.established_bs} BS`);
  document.querySelectorAll('.school-phone').forEach(el => el.textContent = info.phone);
  document.querySelectorAll('.school-email').forEach(el => el.textContent = info.email);

  if (info.stats) {
    const s = info.stats;
    const stCount = document.getElementById('stat-students-count');
    if (stCount) stCount.textContent = `${s.active_students}+`;
    const staffCount = document.getElementById('stat-staff-count');
    if (staffCount) staffCount.textContent = `${s.active_staff}+`;
    const classesCount = document.getElementById('stat-classes-count');
    if (classesCount) classesCount.textContent = `${s.total_classes}`;
    
    const cardSt = document.getElementById('dash-card-students');
    if (cardSt) cardSt.textContent = s.active_students;
    const cardStaff = document.getElementById('dash-card-staff');
    if (cardStaff) cardStaff.textContent = s.active_staff;
    const cardFee = document.getElementById('dash-card-collected');
    if (cardFee) cardFee.textContent = `NPR ${Number(s.total_fee_collected).toLocaleString()}`;
    const cardDues = document.getElementById('dash-card-due');
    if (cardDues) cardDues.textContent = `NPR ${Number(s.total_fee_due).toLocaleString()}`;
  }
}

function populateClassDropdowns(classes) {
  const selects = document.querySelectorAll('.class-select-dropdown');
  selects.forEach(sel => {
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">-- All Classes --</option>';
    classes.forEach(c => {
      sel.innerHTML += `<option value="${c.id}">${c.name} (${c.level})</option>`;
    });
    if (currentVal) sel.value = currentVal;
  });
}

// Dashboard Data
async function loadDashboardData() {
  await fetchSchoolInfo();
  
  if (State.currentUser && State.currentUser.role === 'teacher') {
    return; // Teacher doesn't see financial transactions
  }

  try {
    const res = await apiFetch('/api/finance/summary');
    const data = await res.json();
    const tbody = document.getElementById('dash-recent-payments-tbody');
    if (tbody) {
      if (data.recent_payments && data.recent_payments.length > 0) {
        tbody.innerHTML = data.recent_payments.map(p => `
          <tr>
            <td class="font-bold">${p.receipt_no}</td>
            <td>${p.first_name} ${p.last_name}</td>
            <td><span class="badge badge-info">${p.class_name}</span></td>
            <td class="font-bold text-success">NPR ${Number(p.amount_paid).toLocaleString()}</td>
            <td><span class="badge badge-neutral">${p.payment_mode}</span></td>
            <td>${p.payment_date}</td>
          </tr>
        `).join('');
      } else {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No recent transactions</td></tr>`;
      }
    }
  } catch (err) {
    console.error('Dashboard load:', err);
  }
}

// Dedicated Student & Parent Portal View
async function loadStudentPortalView() {
  if (!State.currentUser || State.currentUser.role !== 'student') return;
  const sid = State.currentUser.linked_student_id;

  try {
    const res = await apiFetch(`/api/students/${sid}`);
    const st = await res.json();

    const portalHeader = document.getElementById('sp-student-header');
    if (portalHeader) {
      portalHeader.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
          <div style="display: flex; gap: 1.5rem; align-items: center;">
            <div style="width: 70px; height: 70px; border-radius: 50%; background: #1e3a8a; color: white; display: flex; align-items: center; justify-content: center; font-size: 2rem; font-weight: bold;">
              🎓
            </div>
            <div>
              <h2 style="font-size: 1.5rem; font-weight: 800; color: #1e3a8a;">${st.first_name} ${st.last_name}</h2>
              <div style="font-size: 0.9rem; color: #0f766e; font-weight: 600;">${st.name_np || ''}</div>
              <div style="display: flex; gap: 0.5rem; margin-top: 0.35rem; flex-wrap: wrap;">
                <span class="badge badge-info">Class: ${st.class_name} (${st.section_name})</span>
                <span class="badge badge-neutral">Roll: ${st.roll_no}</span>
                <span class="badge badge-success">Reg: ${st.reg_no}</span>
                <span class="badge badge-warning">Blood: ${st.blood_group || 'N/A'}</span>
              </div>
            </div>
          </div>
          <div>
            <button class="btn btn-outline btn-sm" onclick="openModal('change-password-modal')" style="border-color: #cbd5e1; font-size: 0.82rem;">
              🔑 Change Password
            </button>
          </div>
        </div>
      `;
    }

    // Populate student portal exams dropdown
    const resExams = await apiFetch('/api/exams');
    const exams = await resExams.json();
    const exSel = document.getElementById('sp-exam-select');
    if (exSel) {
      exSel.innerHTML = exams.map(e => `<option value="${e.id}">${e.name} (${e.academic_year})</option>`).join('');
    }

    // Auto-generate grade sheet
    loadStudentPortalGradeSheet();

    // Populate student fee invoices
    const resInv = await apiFetch(`/api/finance/invoices?student_id=${sid}`);
    const invoices = await resInv.json();
    const invTbody = document.getElementById('sp-invoices-tbody');
    if (invTbody) {
      if (invoices.length === 0) {
        invTbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No fee records found.</td></tr>';
      } else {
        invTbody.innerHTML = invoices.map(inv => {
          const net = inv.total_amount + inv.fine - inv.discount;
          const due = Math.max(0, net - inv.paid_amount);
          return `
            <tr>
              <td class="font-bold">${inv.invoice_no}</td>
              <td>${inv.month} ${inv.year}</td>
              <td class="font-bold">NPR ${Number(net).toLocaleString()}</td>
              <td class="text-success font-bold">NPR ${Number(inv.paid_amount).toLocaleString()}</td>
              <td class="font-bold ${due > 0 ? 'text-danger' : 'text-success'}">NPR ${Number(due).toLocaleString()}</td>
              <td>
                <span class="badge ${inv.status === 'Paid' ? 'badge-success' : (inv.status === 'Partially Paid' ? 'badge-warning' : 'badge-danger')}">${inv.status}</span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

  } catch (err) {
    showToast('Failed to load student portal data', 'error');
  }
}

async function loadStudentPortalGradeSheet() {
  if (!State.currentUser || State.currentUser.role !== 'student') return;
  const sid = State.currentUser.linked_student_id;
  const exSel = document.getElementById('sp-exam-select');
  const container = document.getElementById('sp-gradesheet-container');

  if (!exSel || !container) return;
  const examId = exSel.value;
  if (!examId) return;

  container.innerHTML = '<div style="text-align: center; padding: 2rem;">Loading certified grade sheet...</div>';

  try {
    const res = await apiFetch(`/api/gradesheet?student_id=${sid}&exam_id=${examId}`);
    const data = await res.json();
    const { school, student, exam, subjects, summary } = data;

    container.innerHTML = `
      <div class="printable-area">
        <div class="gradesheet-container">
          <div class="gradesheet-watermark">SAGARMATHA</div>

          <div class="gs-header">
            <div class="gs-nepal-sub">नेपाल सरकार | Government of Nepal</div>
            <div class="gs-nepal-sub">शिक्षा, विज्ञान तथा प्रविधि मन्त्रालय | Ministry of Education, Science and Technology</div>
            <div class="gs-school-name-np">${school.name_np}</div>
            <div class="gs-school-name-en">${school.name_en}</div>
            <div class="gs-school-address">${school.address_np} / ${school.address_en}</div>
            <div class="gs-estd">Estd. ${school.established_bs} B.S. | Centrally Located Community School</div>
            
            <div class="gs-title-box">
              <span class="gs-nepali-title">लब्धाङ्क पत्र</span>
              GRADE-SHEET
            </div>
            <div style="font-size: 0.85rem; font-weight: bold; margin-top: 0.35rem; color: #1e3a8a;">
              ${exam.name} - ${exam.academic_year}
            </div>
          </div>

          <div class="gs-student-info">
            <div class="gs-info-row">
              <span class="gs-info-label">Student's Name:</span>
              <span class="gs-info-val">${student.first_name} ${student.last_name} (${student.name_np || ''})</span>
            </div>
            <div class="gs-info-row">
              <span class="gs-info-label">Registration No:</span>
              <span class="gs-info-val">${student.reg_no}</span>
            </div>
            <div class="gs-info-row">
              <span class="gs-info-label">Class / Stream:</span>
              <span class="gs-info-val">${student.class_name} (Sec: ${student.section_name})</span>
            </div>
            <div class="gs-info-row">
              <span class="gs-info-label">Roll Number:</span>
              <span class="gs-info-val">${student.roll_no}</span>
            </div>
            <div class="gs-info-row">
              <span class="gs-info-label">Date of Birth (BS):</span>
              <span class="gs-info-val">${student.dob_bs}</span>
            </div>
            <div class="gs-info-row">
              <span class="gs-info-label">Date of Birth (AD):</span>
              <span class="gs-info-val">${student.dob_ad || 'N/A'}</span>
            </div>
          </div>

          <table class="gs-table">
            <thead>
              <tr>
                <th rowspan="2" style="width: 70px;">Subject Code</th>
                <th rowspan="2">Subject Title</th>
                <th rowspan="2" style="width: 55px;">Credit Hour (CH)</th>
                <th colspan="2">Obtained Grade</th>
                <th rowspan="2" style="width: 60px;">Final Grade</th>
                <th rowspan="2" style="width: 60px;">Grade Point (GP)</th>
                <th rowspan="2" style="width: 80px;">Remarks</th>
              </tr>
              <tr>
                <th style="width: 65px;">Theory (TH)</th>
                <th style="width: 65px;">Internal / Pract (PR)</th>
              </tr>
            </thead>
            <tbody>
              ${subjects.map(s => `
                <tr>
                  <td class="font-bold">${s.code}</td>
                  <td class="text-left">
                    <span style="font-weight: 600;">${s.name_en}</span>
                    ${s.name_np ? `<div class="th-sub">${s.name_np}</div>` : ''}
                  </td>
                  <td>${s.credit_hours.toFixed(1)}</td>
                  <td>${s.theory_grade}</td>
                  <td>${s.practical_grade}</td>
                  <td class="font-bold ${s.final_grade === 'NG' ? 'text-danger' : ''}">${s.final_grade}</td>
                  <td class="font-bold">${s.final_gp.toFixed(2)}</td>
                  <td style="font-size: 0.78rem;">${s.remarks}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>

          <div class="gs-result-card">
            <div>
              <div class="gs-gpa-display">
                Grade Point Average (GPA): 
                <span class="gs-gpa-number ${summary.has_ng ? 'text-danger' : ''}">${summary.gpa_display}</span>
              </div>
              <div class="gs-remarks-display">
                <strong>Result Status:</strong> ${summary.result_status}
              </div>
              <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.2rem;">
                ${summary.result_remarks}
              </div>
            </div>
            
            <div style="text-align: center; border: 1px solid #cbd5e1; padding: 0.4rem 0.6rem; border-radius: 4px; background: white;">
              <div style="font-size: 0.68rem; font-weight: bold; color: #1e3a8a;">SECURE VERIFIED</div>
              <div style="font-family: monospace; font-size: 1.2rem; letter-spacing: 2px;">[QR-VERIFY]</div>
              <div style="font-size: 0.65rem; color: #64748b;">${student.reg_no}</div>
            </div>
          </div>

          <div class="gs-signatures">
            <div class="gs-sign-col"><div class="gs-sign-line">Class Teacher</div></div>
            <div class="gs-sign-col"><div class="gs-sign-line">Exam Coordinator</div></div>
            <div class="gs-sign-col"><div class="gs-sign-line">Headmaster / Principal</div></div>
          </div>

          <div style="font-size: 0.7rem; color: #94a3b8; text-align: center; margin-top: 1.5rem;">
            Certified Official Grade-Sheet | Sagarmatha EMS | Bhadrapur 2, Jhapa
          </div>
        </div>
      </div>

      <div class="no-print" style="margin-top: 1.5rem; text-align: center;">
        <button class="btn btn-primary" onclick="window.print()">🖨️ Print My Grade Sheet</button>
      </div>
    `;
  } catch (err) {
    container.innerHTML = '<div style="color: red; padding: 2rem;">Failed to load grade sheet.</div>';
  }
}

// Global App Initialization
document.addEventListener('DOMContentLoaded', () => {
  fetchSchoolInfo();
  fetchClasses();
  checkAuthStatus();

  // Login Form Submission
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = loginForm.querySelector('button[type="submit"]');
      const errBox = document.getElementById('login-error-msg');
      if (errBox) errBox.style.display = 'none';
      btn.disabled = true;

      await loginUser(loginForm.username.value.trim(), loginForm.password.value);
      btn.disabled = false;
    });
  }

  // Modals backdrop close
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('open');
      }
    });
  });

  // ESC key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
    }
  });

  // Sidebar item navigation
  document.querySelectorAll('.sidebar-item').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;
      if (view) switchView(view);
    });
  });
});

// -------------------------------------------------------------
// Password Change Handlers
// -------------------------------------------------------------
function togglePasswordVisibility() {
  const toggle = document.getElementById('show-password-toggle');
  const ids = ['cp-current', 'cp-new', 'cp-confirm'];
  ids.forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.type = toggle && toggle.checked ? 'text' : 'password';
    }
  });
}

async function handleChangePasswordSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const current_password = form.current_password.value.trim();
  const new_password = form.new_password.value.trim();
  const confirm_password = form.confirm_password.value.trim();

  if (!current_password || !new_password) {
    showToast('Please enter both current and new passwords.', 'error');
    return;
  }

  if (new_password.length < 6) {
    showToast('New password must be at least 6 characters.', 'error');
    return;
  }

  if (new_password !== confirm_password) {
    showToast('New passwords do not match. Please verify.', 'error');
    return;
  }

  const btn = document.getElementById('save-password-btn');
  const originalText = btn ? btn.textContent : 'Update Password';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Updating...';
  }

  try {
    const res = await apiFetch('/api/auth/change-password', {
      method: 'POST',
      body: {
        current_password,
        new_password
      }
    });

    const data = await res.json();
    if (data.success) {
      showToast('Your password has been successfully updated!', 'success');
      closeModal('change-password-modal');
      form.reset();
      const toggle = document.getElementById('show-password-toggle');
      if (toggle) toggle.checked = false;
      togglePasswordVisibility();
    } else {
      showToast(data.error || 'Failed to update password.', 'error');
    }
  } catch (err) {
    console.error('Password change error:', err);
    showToast('Network error while changing password.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }
}

