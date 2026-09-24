/**
 * reports.js - Staff, Daily Attendance, Public Notices & Admission Inquiries management
 */

// Staff / Teachers
async function loadStaffView() {
  const tbody = document.getElementById('staff-table-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading faculty & staff directory...</td></tr>';

  try {
    const res = await fetch('/api/staff');
    const staff = await res.json();

    if (staff.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No staff records found.</td></tr>';
      return;
    }

    tbody.innerHTML = staff.map(s => `
      <tr>
        <td class="font-bold">${s.emp_code}</td>
        <td>
          <div style="font-weight: 700;">${s.name_en}</div>
          ${s.name_np ? `<div style="font-size: 0.78rem; color: #0f766e;">${s.name_np}</div>` : ''}
        </td>
        <td class="font-bold text-primary">${s.role}</td>
        <td><span class="badge badge-info">${s.department}</span></td>
        <td>${s.qualification}</td>
        <td>📞 ${s.phone}</td>
        <td><span class="badge ${s.status === 'Active' ? 'badge-success' : 'badge-neutral'}">${s.status}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load staff list.</td></tr>';
  }
}

// Daily Attendance
async function loadAttendanceView() {
  const classSel = document.getElementById('att-class-select');
  const dateInput = document.getElementById('att-date-input');
  const tbody = document.getElementById('attendance-table-tbody');

  if (!classSel || !dateInput || !tbody) return;

  if (!dateInput.value) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
  }

  // Default to Class 10 if none chosen
  if (!classSel.value && State.classes.length > 0) {
    const c10 = State.classes.find(c => c.name === 'Class 10') || State.classes[0];
    classSel.value = c10.id;
  }

  const cid = classSel.value;
  const date = dateInput.value;

  if (!cid) return;

  tbody.innerHTML = '<tr><td colspan="6" class="text-center">Loading class attendance register...</td></tr>';

  try {
    const res = await fetch(`/api/attendance?class_id=${cid}&date=${date}`);
    const rows = await res.json();

    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No active students in this class.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(r => `
      <tr data-student-id="${r.student_id}">
        <td class="font-bold">${r.roll_no}</td>
        <td>${r.reg_no}</td>
        <td class="font-bold">${r.first_name} ${r.last_name}</td>
        <td>
          <div style="display: flex; gap: 0.75rem;">
            <label style="display: flex; align-items: center; gap: 0.25rem; cursor: pointer; color: #15803d; font-weight: 600;">
              <input type="radio" name="att_${r.student_id}" value="Present" ${r.attendance_status === 'Present' ? 'checked' : ''}> Present
            </label>
            <label style="display: flex; align-items: center; gap: 0.25rem; cursor: pointer; color: #dc2626; font-weight: 600;">
              <input type="radio" name="att_${r.student_id}" value="Absent" ${r.attendance_status === 'Absent' ? 'checked' : ''}> Absent
            </label>
            <label style="display: flex; align-items: center; gap: 0.25rem; cursor: pointer; color: #d97706; font-weight: 600;">
              <input type="radio" name="att_${r.student_id}" value="Leave" ${r.attendance_status === 'Leave' ? 'checked' : ''}> Leave
            </label>
          </div>
        </td>
        <td>
          <input type="text" class="form-control att-remarks-input" placeholder="Remarks..." value="${r.remarks || ''}" style="padding: 0.25rem 0.5rem; font-size: 0.82rem;">
        </td>
      </tr>
    `).join('');

  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load attendance.</td></tr>';
  }
}

async function saveDailyAttendance() {
  const classSel = document.getElementById('att-class-select');
  const dateInput = document.getElementById('att-date-input');
  const tbody = document.getElementById('attendance-table-tbody');

  const rows = tbody.querySelectorAll('tr[data-student-id]');
  const list = [];

  rows.forEach(tr => {
    const sid = tr.dataset.studentId;
    const checkedRadio = tr.querySelector(`input[name="att_${sid}"]:checked`);
    const status = checkedRadio ? checkedRadio.value : 'Present';
    const remarks = tr.querySelector('.att-remarks-input').value.trim();
    list.push({ student_id: sid, status, remarks });
  });

  try {
    const res = await fetch('/api/attendance/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: dateInput.value,
        attendance: list
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Daily attendance saved successfully!', 'success');
    } else {
      showToast(data.error || 'Failed to save attendance', 'error');
    }
  } catch (err) {
    showToast('Network error saving attendance', 'error');
  }
}

// Notices EMS
async function loadNoticesEMS() {
  const tbody = document.getElementById('ems-notices-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="text-center">Loading notices...</td></tr>';

  try {
    const res = await fetch('/api/notices');
    const notices = await res.json();

    tbody.innerHTML = notices.map(n => `
      <tr>
        <td class="font-bold">${n.posted_date}</td>
        <td>
          <div style="font-weight: 700;">${n.title}</div>
          <div style="font-size: 0.8rem; color: #64748b;">${n.content.substring(0, 80)}...</div>
        </td>
        <td><span class="badge badge-info">${n.category}</span></td>
        <td>${n.is_pinned ? '<span class="badge badge-warning">📌 Pinned</span>' : 'Standard'}</td>
        <td>${n.file_attachment ? `📎 ${n.file_attachment}` : 'None'}</td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load notices.</td></tr>';
  }
}

// Admission Inquiries EMS
async function loadInquiriesEMS() {
  const tbody = document.getElementById('ems-inquiries-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading student admission inquiries...</td></tr>';

  try {
    const res = await fetch('/api/inquiries');
    const inquiries = await res.json();

    if (inquiries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No admission inquiries submitted yet.</td></tr>';
      return;
    }

    tbody.innerHTML = inquiries.map(inq => {
      const statusBadge = inq.status === 'Admitted' ? 'badge-success' : (inq.status === 'Contacted' ? 'badge-info' : 'badge-warning');
      return `
        <tr>
          <td class="font-bold">${inq.applicant_name}</td>
          <td><span class="badge badge-info">${inq.applying_class}</span></td>
          <td>
            <div>${inq.guardian_name}</div>
            <div style="font-size: 0.78rem; color: #64748b;">📞 ${inq.phone}</div>
          </td>
          <td>${inq.address}</td>
          <td style="font-size: 0.82rem; color: #475569;">${inq.message || 'Standard inquiry'}</td>
          <td><span class="badge ${statusBadge}">${inq.status}</span></td>
          <td>
            <select class="form-control" style="font-size: 0.78rem; padding: 0.2rem;" onchange="updateInquiryStatus(${inq.id}, this.value)">
              <option value="Pending" ${inq.status === 'Pending' ? 'selected' : ''}>Pending</option>
              <option value="Contacted" ${inq.status === 'Contacted' ? 'selected' : ''}>Contacted</option>
              <option value="Admitted" ${inq.status === 'Admitted' ? 'selected' : ''}>Admitted</option>
              <option value="Rejected" ${inq.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
            </select>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load inquiries.</td></tr>';
  }
}

async function updateInquiryStatus(inqId, newStatus) {
  try {
    const res = await fetch(`/api/inquiries/${inqId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Inquiry marked as ${newStatus}`, 'success');
      loadInquiriesEMS();
    }
  } catch (err) {
    showToast('Failed to update status', 'error');
  }
}

// Add Staff Form Submission
document.addEventListener('DOMContentLoaded', () => {
  const staffForm = document.getElementById('add-staff-form');
  if (staffForm) {
    staffForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = staffForm.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        emp_code: staffForm.emp_code.value.trim(),
        name_en: staffForm.name_en.value.trim(),
        name_np: staffForm.name_np.value.trim(),
        role: staffForm.role.value.trim(),
        department: staffForm.department.value,
        qualification: staffForm.qualification.value.trim(),
        phone: staffForm.phone.value.trim(),
        email: staffForm.email.value.trim(),
        status: 'Active'
      };

      try {
        const res = await fetch('/api/staff', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('Staff member added successfully!', 'success');
          closeModal('add-staff-modal');
          staffForm.reset();
          loadStaffView();
          fetchSchoolInfo();
        } else {
          showToast(data.error || 'Failed to add staff', 'error');
        }
      } catch (err) {
        showToast('Network error adding staff', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Add Notice Form Submission
  const noticeForm = document.getElementById('add-notice-form');
  if (noticeForm) {
    noticeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = noticeForm.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        title: noticeForm.title.value.trim(),
        category: noticeForm.category.value,
        content: noticeForm.content.value.trim(),
        is_pinned: noticeForm.is_pinned.checked ? 1 : 0,
        file_attachment: noticeForm.file_attachment.value.trim()
      };

      try {
        const res = await fetch('/api/notices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('Notice published successfully!', 'success');
          closeModal('add-notice-modal');
          noticeForm.reset();
          loadNoticesEMS();
          loadPublicNotices();
        } else {
          showToast(data.error || 'Failed to publish notice', 'error');
        }
      } catch (err) {
        showToast('Network error publishing notice', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }
});
