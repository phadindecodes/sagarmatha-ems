/**
 * students.js - Student Information System (SIS) for Sagarmatha EMS
 */

let currentStudentsList = [];

async function loadStudentsView() {
  const classFilter = document.getElementById('student-filter-class');
  const sectionFilter = document.getElementById('student-filter-section');
  const searchInput = document.getElementById('student-search-input');

  const cid = classFilter ? classFilter.value : '';
  const secId = sectionFilter ? sectionFilter.value : '';
  const search = searchInput ? searchInput.value.trim() : '';

  const tbody = document.getElementById('students-table-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem;">Loading student directory...</td></tr>';
  }

  try {
    let url = `/api/students?class_id=${cid}&section_id=${secId}&search=${encodeURIComponent(search)}`;
    const res = await fetch(url);
    const data = await res.json();
    currentStudentsList = data;
    renderStudentsTable(data);
  } catch (err) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Failed to load students.</td></tr>';
  }
}

function renderStudentsTable(students) {
  const tbody = document.getElementById('students-table-tbody');
  const counter = document.getElementById('students-count-badge');
  if (counter) counter.textContent = `${students.length} Students`;

  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem; color: #64748b;">No students found matching your criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = students.map(s => `
    <tr>
      <td class="font-bold">
        <div>${s.reg_no}</div>
        ${s.portal_username ? `<span class="badge badge-success" style="font-size: 0.68rem; margin-top: 3px; display: inline-block;" title="Portal Login Username: ${s.portal_username}">🔑 ${s.portal_username}</span>` : `<span class="badge badge-neutral" style="font-size: 0.68rem; margin-top: 3px; display: inline-block;" title="No portal account yet">No login</span>`}
      </td>
      <td><strong>${s.roll_no}</strong></td>
      <td>
        <div style="font-weight: 700; color: #0f172a;">${s.first_name} ${s.last_name}</div>
        ${s.name_np ? `<div style="font-size: 0.78rem; color: #0f766e;">${s.name_np}</div>` : ''}
      </td>
      <td><span class="badge badge-info">${s.class_name} - ${s.section_name}</span></td>
      <td>${s.gender}</td>
      <td>
        <div>${s.guardian_name} (${s.guardian_relation})</div>
        <div style="font-size: 0.78rem; color: #64748b;">📞 ${s.guardian_phone}</div>
      </td>
      <td>
        <span class="badge ${s.status === 'Active' ? 'badge-success' : 'badge-neutral'}">${s.status}</span>
      </td>
      <td>
        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
          <button class="btn btn-secondary btn-sm" onclick="viewStudentProfile(${s.id})" title="View Profile">
            👁️
          </button>
          <button class="btn btn-primary btn-sm" onclick="openStudentIdCard(${s.id})" title="ID Card">
            🪪 ID
          </button>
          <button class="btn btn-accent btn-sm" onclick="generateStudentMarksheet(${s.id})" title="Grade Sheet">
            📄 Grade
          </button>
          ${s.portal_user_id ? `
            <button class="btn btn-outline btn-sm" onclick="openAdminResetPasswordModal(${s.portal_user_id}, '${s.portal_username}')" title="Reset Student Portal Password">
              🔑
            </button>
          ` : `
            <button class="btn btn-neutral btn-sm" onclick="quickCreateStudentAccount(${s.id}, '${s.reg_no}', '${s.first_name} ${s.last_name}')" title="Generate Portal Account">
              ➕🔑
            </button>
          `}
        </div>
      </td>
    </tr>
  `).join('');
}

async function quickCreateStudentAccount(studentId, regNo, studentName) {
  if (!confirm(`Create portal login account for student "${studentName}" with username "${regNo}" and default password "sagarmatha@2081"?`)) {
    return;
  }
  try {
    const res = await fetch('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: regNo,
        password: 'sagarmatha@2081',
        full_name: studentName,
        role: 'student',
        linked_student_id: studentId
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Student portal account created for ${regNo}`, 'success');
      loadStudentsView();
    } else {
      showToast(data.error || 'Failed to create student account', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server', 'error');
  }
}

async function viewStudentProfile(id) {
  try {
    const res = await fetch(`/api/students/${id}`);
    const st = await res.json();

    const body = document.getElementById('student-profile-modal-body');
    if (!body) return;

    body.innerHTML = `
      <div style="display: grid; grid-template-columns: 120px 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
        <div style="width: 120px; height: 120px; background: #e0e7ff; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 3rem; color: #1e3a8a;">
          👤
        </div>
        <div>
          <h3 style="font-size: 1.35rem; font-weight: 800; color: #1e3a8a;">${st.first_name} ${st.last_name}</h3>
          <p style="font-size: 0.95rem; color: #0f766e; font-weight: 600;">${st.name_np || ''}</p>
          <div style="display: flex; gap: 0.6rem; margin-top: 0.5rem; flex-wrap: wrap;">
            <span class="badge badge-info">Class: ${st.class_name} (${st.section_name})</span>
            <span class="badge badge-neutral">Roll: ${st.roll_no}</span>
            <span class="badge badge-success">Reg: ${st.reg_no}</span>
            <span class="badge badge-warning">Blood: ${st.blood_group || 'N/A'}</span>
          </div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 0.9rem;">
        <div><strong>Date of Birth (BS):</strong> ${st.dob_bs}</div>
        <div><strong>Date of Birth (AD):</strong> ${st.dob_ad || 'N/A'}</div>
        <div><strong>Gender:</strong> ${st.gender}</div>
        <div><strong>Permanent Address:</strong> ${st.address}</div>
        <div><strong>Guardian Name:</strong> ${st.guardian_name} (${st.guardian_relation})</div>
        <div><strong>Guardian Phone:</strong> ${st.guardian_phone}</div>
        <div><strong>Admission Date:</strong> ${st.admission_date || 'N/A'}</div>
        <div><strong>Status:</strong> ${st.status}</div>
        <div><strong>Portal Login Account:</strong> ${st.portal_username ? `<span class="badge badge-success">Active (${st.portal_username})</span>` : '<span class="badge badge-neutral">No account</span>'}</div>
      </div>
    `;

    openModal('student-profile-modal');
  } catch (err) {
    showToast('Failed to load student profile', 'error');
  }
}

async function openStudentIdCard(id) {
  try {
    const res = await fetch(`/api/students/${id}`);
    const st = await res.json();
    const info = State.schoolInfo || {};

    const container = document.getElementById('student-id-card-content');
    if (!container) return;

    container.innerHTML = `
      <div style="width: 340px; margin: 0 auto; border: 2px solid #1e3a8a; border-radius: 12px; overflow: hidden; background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <!-- ID Header -->
        <div style="background: linear-gradient(135deg, #1e3a8a, #0f766e); color: white; padding: 0.8rem; text-align: center;">
          <h4 style="font-size: 0.95rem; font-weight: 800; letter-spacing: 0.02em;">${info.name_en || 'SHREE SAGARMATHA SEC. SCHOOL'}</h4>
          <p style="font-size: 0.72rem; opacity: 0.9;">${info.address_en || 'Bhadrapur-2, Jhapa'} (Estd. 2034 BS)</p>
          <div style="background: #fbbf24; color: #000; font-size: 0.7rem; font-weight: bold; padding: 0.15rem 0.6rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem;">
            STUDENT IDENTITY CARD
          </div>
        </div>

        <!-- ID Body -->
        <div style="padding: 1.25rem 1rem; text-align: center;">
          <div style="width: 80px; height: 90px; border: 2px solid #cbd5e1; border-radius: 8px; margin: 0 auto 0.75rem; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; background: #f8fafc;">
            👤
          </div>
          <h3 style="font-size: 1.15rem; font-weight: bold; color: #0f172a;">${st.first_name} ${st.last_name}</h3>
          <p style="font-size: 0.85rem; color: #0f766e; font-weight: 600;">${st.name_np || ''}</p>

          <div style="text-align: left; font-size: 0.82rem; margin-top: 0.85rem; background: #f8fafc; padding: 0.6rem 0.8rem; border-radius: 6px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 0.25rem;">
            <div><strong>Class:</strong> ${st.class_name} | <strong>Sec:</strong> ${st.section_name}</div>
            <div><strong>Roll No:</strong> ${st.roll_no} | <strong>Reg:</strong> ${st.reg_no}</div>
            <div><strong>DOB (BS):</strong> ${st.dob_bs}</div>
            <div><strong>Blood Group:</strong> <span style="color: red; font-weight: bold;">${st.blood_group || 'N/A'}</span></div>
            <div><strong>Guardian:</strong> ${st.guardian_name} (${st.guardian_phone})</div>
          </div>

          <!-- Barcode dummy -->
          <div style="margin-top: 1rem; font-family: monospace; font-size: 1.1rem; letter-spacing: 4px; color: #334155;">
            ||||| | |||| ||| |||||
          </div>
          <div style="font-size: 0.7rem; color: #64748b;">Academic Session 2081-2082</div>
        </div>

        <!-- ID Footer -->
        <div style="background: #f1f5f9; padding: 0.5rem 1rem; display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid #e2e8f0;">
          <span style="font-size: 0.68rem; color: #64748b;">Card Holder</span>
          <div style="text-align: center;">
            <div style="border-bottom: 1px solid #334155; width: 90px; margin-bottom: 0.15rem;"></div>
            <span style="font-size: 0.68rem; font-weight: bold;">Headmaster</span>
          </div>
        </div>
      </div>
    `;

    openModal('student-id-card-modal');
  } catch (err) {
    showToast('Failed to load student card', 'error');
  }
}

// Student Form Submission
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('add-student-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        reg_no: form.reg_no.value.trim(),
        roll_no: form.roll_no.value,
        first_name: form.first_name.value.trim(),
        last_name: form.last_name.value.trim(),
        name_np: form.name_np.value.trim(),
        gender: form.gender.value,
        dob_bs: form.dob_bs.value.trim(),
        dob_ad: form.dob_ad.value.trim(),
        class_id: form.class_id.value,
        section_id: form.section_id.value,
        guardian_name: form.guardian_name.value.trim(),
        guardian_relation: form.guardian_relation.value,
        guardian_phone: form.guardian_phone.value.trim(),
        address: form.address.value.trim(),
        blood_group: form.blood_group.value,
        status: 'Active'
      };

      try {
        const res = await fetch('/api/students', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('Student registered successfully!', 'success');
          closeModal('add-student-modal');
          form.reset();
          loadStudentsView();
          fetchSchoolInfo(); // Update counts
        } else {
          showToast(data.error || 'Failed to save student', 'error');
        }
      } catch (err) {
        showToast('Error communicating with server', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Dynamic class to section selector in Add Student modal
  const classSel = document.getElementById('modal-student-class-id');
  if (classSel) {
    classSel.addEventListener('change', async () => {
      const cid = classSel.value;
      const secSel = document.getElementById('modal-student-section-id');
      if (!secSel) return;
      secSel.innerHTML = '<option value="">Loading sections...</option>';
      if (!cid) {
        secSel.innerHTML = '<option value="">-- Select Class First --</option>';
        return;
      }
      try {
        const res = await fetch(`/api/sections?class_id=${cid}`);
        const secs = await res.json();
        secSel.innerHTML = secs.map(s => `<option value="${s.id}">Section ${s.name}</option>`).join('');
      } catch (err) {
        secSel.innerHTML = '<option value="">Error loading sections</option>';
      }
    });
  }
});
