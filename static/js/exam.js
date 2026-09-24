/**
 * exam.js - Examination Management & Nepal CDC Grade Sheet Preparation
 * Follows Nepal CDC Letter Grading Directive 2078/2080 (अक्षरांकन निर्देशिका)
 */

let examData = {
  exams: [],
  subjects: [],
  marks: [],
  activeExamId: null,
  activeClassId: null,
  activeSubjectId: null
};

function populateExamClassDropdowns() {
  if (!State.classes || State.classes.length === 0) return;

  const targetSelectIds = ['exam-marks-class-select', 'gs-class-select', 'ledger-class-select', 'sub-dir-class-select', 'new-subject-class-select'];
  targetSelectIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const curVal = el.value;
    el.innerHTML = State.classes.map(c => `<option value="${c.id}">${c.name} (${c.level})</option>`).join('');
    if (curVal && State.classes.some(c => String(c.id) === String(curVal))) {
      el.value = curVal;
    } else {
      const c10 = State.classes.find(c => c.name === 'Class 10');
      if (c10) el.value = c10.id;
      else if (State.classes.length > 0) el.value = State.classes[0].id;
    }
  });
}

async function loadExamView(preselectedStudentId = null) {
  try {
    // 1. Ensure classes are loaded
    if (!State.classes || State.classes.length === 0) {
      await fetchClasses();
    }

    // 2. Populate Class dropdowns specifically for Exam Marks, Ledger, and Directory
    populateExamClassDropdowns();

    // 3. Populate Exam list
    const res = await fetch('/api/exams');
    examData.exams = await res.json();
    
    const examSelects = document.querySelectorAll('.exam-select-dropdown');
    examSelects.forEach(sel => {
      const cur = sel.value;
      sel.innerHTML = examData.exams.map(e => `<option value="${e.id}">${e.name} (${e.academic_year})</option>`).join('');
      if (cur && examData.exams.some(e => String(e.id) === String(cur))) {
        sel.value = cur;
      }
    });

    if (examData.exams.length > 0 && !examData.activeExamId) {
      examData.activeExamId = examData.exams[0].id;
    }

    // Ensure default Class 10 or first class is selected
    const classSel = document.getElementById('exam-marks-class-select');
    if (classSel && (!classSel.value || classSel.value === '')) {
      const c10 = State.classes.find(c => c.name === 'Class 10');
      if (c10) classSel.value = c10.id;
      else if (State.classes.length > 0) classSel.value = State.classes[0].id;
    }

    const gsClassSel = document.getElementById('gs-class-select');
    if (gsClassSel && (!gsClassSel.value || gsClassSel.value === '')) {
      const c10 = State.classes.find(c => c.name === 'Class 10');
      if (c10) gsClassSel.value = c10.id;
      else if (State.classes.length > 0) gsClassSel.value = State.classes[0].id;
      await populateGradeSheetStudentDropdown(gsClassSel.value);
    }

    await onExamClassChanged();

    // Also populate Subject Directory if container exists
    loadClassSubjectsDirectory();

    if (preselectedStudentId) {
      switchExamSubTab('gradesheet');
      const stSel = document.getElementById('gs-student-select');
      if (stSel) {
        stSel.value = preselectedStudentId;
        generateOfficialGradeSheet();
      }
    }
  } catch (err) {
    console.error('Failed to load exam data:', err);
  }
}

function switchExamSubTab(tabName) {
  document.querySelectorAll('.exam-tab-btn').forEach(btn => {
    if (btn.dataset.tab === tabName) btn.classList.add('active');
    else btn.classList.remove('active');
  });

  document.querySelectorAll('.exam-sub-view').forEach(v => v.style.display = 'none');
  const target = document.getElementById(`exam-sub-${tabName}`);
  if (target) target.style.display = 'block';

  if (tabName === 'ledger') {
    loadClassTabulationLedger();
  } else if (tabName === 'subjects') {
    loadClassSubjectsDirectory();
  }
}

async function onExamClassChanged() {
  const classSel = document.getElementById('exam-marks-class-select');
  const subjectSel = document.getElementById('exam-marks-subject-select');
  if (!classSel || !subjectSel) return;

  const cid = classSel.value;
  if (!cid) {
    subjectSel.innerHTML = '<option value="">-- Select Class First --</option>';
    return;
  }

  try {
    const res = await fetch(`/api/subjects?class_id=${cid}`);
    examData.subjects = await res.json();

    if (examData.subjects && examData.subjects.length > 0) {
      subjectSel.innerHTML = examData.subjects.map(s => `
        <option value="${s.id}">
          ${s.code} - ${s.name_en} (${s.name_np || ''}) [CH: ${s.credit_hours}, Th: ${s.theory_full_marks}, Pr: ${s.practical_full_marks}]
        </option>
      `).join('');
      // Auto-select first subject
      subjectSel.value = examData.subjects[0].id;
    } else {
      subjectSel.innerHTML = '<option value="">-- No Subjects Configured for this Class --</option>';
    }

    // Also populate student dropdown in Grade Sheet generator tab
    populateGradeSheetStudentDropdown(cid);

    await loadSubjectMarksGrid();
  } catch (err) {
    console.error('Failed to load subjects:', err);
  }
}

async function populateGradeSheetStudentDropdown(classId) {
  const gsStudentSelect = document.getElementById('gs-student-select');
  if (!gsStudentSelect) return;

  try {
    const res = await fetch(`/api/students?class_id=${classId}&status=Active`);
    const students = await res.json();
    if (students && students.length > 0) {
      gsStudentSelect.innerHTML = students.map(s => `
        <option value="${s.id}">Roll ${s.roll_no} - ${s.first_name} ${s.last_name} (${s.reg_no})</option>
      `).join('');
    } else {
      gsStudentSelect.innerHTML = '<option value="">-- No Active Students in this Class --</option>';
    }
  } catch (err) {
    console.error('Failed to populate grade sheet student list', err);
  }
}

async function onGradeSheetClassChanged() {
  const gsClassSel = document.getElementById('gs-class-select');
  if (!gsClassSel || !gsClassSel.value) return;
  await populateGradeSheetStudentDropdown(gsClassSel.value);
  generateOfficialGradeSheet();
}

// Bulk Marks Entry Table
async function loadSubjectMarksGrid() {
  const examSel = document.getElementById('exam-marks-exam-select');
  const classSel = document.getElementById('exam-marks-class-select');
  const subjectSel = document.getElementById('exam-marks-subject-select');
  const tbody = document.getElementById('marks-entry-tbody');

  if (!examSel || !classSel || !subjectSel || !tbody) return;

  const examId = examSel.value;
  const classId = classSel.value;
  const subjectId = subjectSel.value;

  if (!examId || !classId || !subjectId) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Please select Exam, Class, and Subject</td></tr>';
    return;
  }

  const curSubject = examData.subjects.find(s => String(s.id) === String(subjectId));
  const thFull = curSubject ? curSubject.theory_full_marks : 75;
  const prFull = curSubject ? curSubject.practical_full_marks : 25;
  const thPass = curSubject ? curSubject.theory_pass_marks : 27;
  const prPass = curSubject ? curSubject.practical_pass_marks : 10;

  document.getElementById('marks-grid-subject-info').innerHTML = `
    <strong>Subject:</strong> ${curSubject ? curSubject.name_en : ''} (${curSubject ? curSubject.code : ''}) | 
    <strong>Credit Hours:</strong> ${curSubject ? curSubject.credit_hours : 4.0} | 
    <strong>Theory:</strong> Full ${thFull} / Pass ${thPass} | 
    <strong>Practical:</strong> Full ${prFull} / Pass ${prPass}
  `;

  tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem;">Loading class mark sheet...</td></tr>';

  try {
    const res = await fetch(`/api/marks?exam_id=${examId}&class_id=${classId}&subject_id=${subjectId}`);
    const rows = await res.json();

    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem;">No active students found in this class.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const th = r.theory_obtained;
      const pr = r.practical_obtained;
      const tot = th + (prFull > 0 ? pr : 0);
      const thPct = thFull > 0 ? (th / thFull * 100) : 0;
      const prPct = prFull > 0 ? (pr / prFull * 100) : 100;
      const isNG = (thPct < 35.0) || (prFull > 0 && prPct < 40.0);

      return `
        <tr data-student-id="${r.student_id}">
          <td class="font-bold">${r.roll_no}</td>
          <td>${r.reg_no}</td>
          <td>
            <div style="font-weight: 700;">${r.first_name} ${r.last_name}</div>
            <div style="font-size: 0.78rem; color: #0f766e;">Sec: ${r.section_name}</div>
          </td>
          <td>
            <input type="number" step="0.5" min="0" max="${thFull}" 
                   class="form-control mark-input-th" 
                   value="${th}" 
                   style="width: 85px; font-weight: bold;"
                   oninput="recalculateRowMarks(this, ${thFull}, ${prFull})">
          </td>
          <td>
            <input type="number" step="0.5" min="0" max="${prFull}" 
                   class="form-control mark-input-pr" 
                   value="${pr}" 
                   ${prFull === 0 ? 'disabled placeholder="N/A"' : ''}
                   style="width: 85px; font-weight: bold;"
                   oninput="recalculateRowMarks(this, ${thFull}, ${prFull})">
          </td>
          <td class="row-total-marks font-bold">${tot}</td>
          <td class="row-grade-badge">
            <span class="badge ${isNG ? 'badge-danger' : 'badge-success'}">${isNG ? 'NG' : 'GRADED'}</span>
          </td>
          <td>
            <button class="btn btn-outline btn-sm" onclick="openStudentQuickGrade(${r.student_id})">
              📄 View Sheet
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Failed to load marks.</td></tr>';
  }
}

function recalculateRowMarks(inputElem, thFull, prFull) {
  const tr = inputElem.closest('tr');
  const thInput = tr.querySelector('.mark-input-th');
  const prInput = tr.querySelector('.mark-input-pr');
  const totalCell = tr.querySelector('.row-total-marks');
  const badgeCell = tr.querySelector('.row-grade-badge');

  const th = parseFloat(thInput.value) || 0;
  const pr = parseFloat(prInput.value) || 0;
  const tot = th + (prFull > 0 ? pr : 0);
  totalCell.textContent = tot.toFixed(1);

  const thPct = (th / thFull) * 100;
  const prPct = prFull > 0 ? (pr / prFull * 100) : 100;
  const isNG = (thPct < 35.0) || (prFull > 0 && prPct < 40.0);

  badgeCell.innerHTML = `<span class="badge ${isNG ? 'badge-danger' : 'badge-success'}">${isNG ? 'NG' : 'GRADED'}</span>`;
}

async function saveAllMarksGrid() {
  const examSel = document.getElementById('exam-marks-exam-select');
  const subjectSel = document.getElementById('exam-marks-subject-select');
  const tbody = document.getElementById('marks-entry-tbody');

  const examId = examSel.value;
  const subjectId = subjectSel.value;

  const rows = tbody.querySelectorAll('tr[data-student-id]');
  const marksPayload = [];

  rows.forEach(tr => {
    const sid = tr.dataset.studentId;
    const th = parseFloat(tr.querySelector('.mark-input-th').value) || 0;
    const pr = parseFloat(tr.querySelector('.mark-input-pr').value) || 0;
    marksPayload.push({
      student_id: sid,
      theory_obtained: th,
      practical_obtained: pr
    });
  });

  const saveBtn = document.getElementById('save-marks-btn');
  const originalText = saveBtn.textContent;
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    const res = await fetch('/api/marks/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exam_id: examId,
        subject_id: subjectId,
        marks: marksPayload
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast('All marks saved & grades recalculated!', 'success');
    } else {
      showToast(result.error || 'Failed to save marks', 'error');
    }
  } catch (err) {
    showToast('Network error saving marks', 'error');
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = originalText;
  }
}

// Official Nepal CDC Grade Sheet Preparation & Printable Layout
async function generateOfficialGradeSheet() {
  const examSel = document.getElementById('gs-exam-select');
  const studentSel = document.getElementById('gs-student-select');
  const container = document.getElementById('official-gradesheet-preview');

  if (!examSel || !studentSel || !container) return;

  const examId = examSel.value;
  const studentId = studentSel.value;

  if (!examId || !studentId) {
    container.innerHTML = '<div style="text-align:center; padding: 3rem; color: #64748b;">Please select an Exam and Student.</div>';
    return;
  }

  container.innerHTML = '<div style="text-align:center; padding: 3rem;">Calculating CDC grades and formatting official marksheet...</div>';

  try {
    const res = await fetch(`/api/gradesheet?student_id=${studentId}&exam_id=${examId}`);
    const data = await res.json();

    if (data.error) {
      container.innerHTML = `<div style="color:red; text-align:center; padding: 2rem;">${data.error}</div>`;
      return;
    }

    const { school, student, exam, subjects, summary } = data;

    container.innerHTML = `
      <div class="printable-area">
        <div class="gradesheet-container">
          <div class="gradesheet-watermark">SAGARMATHA</div>

          <!-- School Header (Official Nepal Pattern) -->
          <div class="gs-header">
            <div class="gs-nepal-sub">नेपाल सरकार | Government of Nepal</div>
            <div class="gs-nepal-sub">शिक्षा, विज्ञान तथा प्रविधि मन्त्रालय | Ministry of Education, Science and Technology</div>
            <div class="gs-school-name-np">${school.name_np}</div>
            <div class="gs-school-name-en">${school.name_en}</div>
            <div class="gs-school-address">${school.address_np} / ${school.address_en}</div>
            <div class="gs-estd">Estd. ${school.established_bs} B.S. (1977 A.D.) | Affiliated to NEB / CDC Nepal</div>
            
            <div class="gs-title-box">
              <span class="gs-nepali-title">लब्धाङ्क पत्र</span>
              GRADE-SHEET
            </div>
            <div style="font-size: 0.85rem; font-weight: bold; margin-top: 0.35rem; color: #1e3a8a;">
              ${exam.name} - ${exam.academic_year}
            </div>
          </div>

          <!-- Student Information Box -->
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

          <!-- CDC Evaluation Table -->
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

          <!-- Result & GPA Summary Box -->
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
            
            <!-- Verification QR Box -->
            <div style="text-align: center; border: 1px solid #cbd5e1; padding: 0.4rem 0.6rem; border-radius: 4px; background: white;">
              <div style="font-size: 0.68rem; font-weight: bold; color: #1e3a8a;">SECURE VERIFIED</div>
              <div style="font-family: monospace; font-size: 1.2rem; letter-spacing: 2px;">[QR-VERIFY]</div>
              <div style="font-size: 0.65rem; color: #64748b;">${student.reg_no}</div>
            </div>
          </div>

          <!-- Nepal Government CDC Letter Grading Scale Legend -->
          <table class="gs-legend-table">
            <thead>
              <tr>
                <th colspan="8" style="background: #e2e8f0; font-weight: bold; font-size: 0.75rem;">
                  NEPAL CDC LETTER GRADING SCALE & DESCRIPTION (अक्षरांकन पद्धति २०७८/२०८०)
                </th>
              </tr>
              <tr>
                <th>Percentage</th>
                <th>Grade</th>
                <th>Grade Point</th>
                <th>Description</th>
                <th>Percentage</th>
                <th>Grade</th>
                <th>Grade Point</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>90% and above</td><td><strong>A+</strong></td><td>4.0</td><td>Outstanding</td>
                <td>50% to &lt;60%</td><td><strong>C+</strong></td><td>2.4</td><td>Satisfactory</td>
              </tr>
              <tr>
                <td>80% to &lt;90%</td><td><strong>A</strong></td><td>3.6</td><td>Excellent</td>
                <td>40% to &lt;50%</td><td><strong>C</strong></td><td>2.0</td><td>Acceptable</td>
              </tr>
              <tr>
                <td>70% to &lt;80%</td><td><strong>B+</strong></td><td>3.2</td><td>Very Good</td>
                <td>35% to &lt;40%</td><td><strong>D</strong></td><td>1.6</td><td>Basic</td>
              </tr>
              <tr>
                <td>60% to &lt;70%</td><td><strong>B</strong></td><td>2.8</td><td>Good</td>
                <td>Below 35%</td><td><strong style="color:red;">NG</strong></td><td>0.0</td><td>Non-Graded</td>
              </tr>
            </tbody>
          </table>

          <!-- Official Signatures -->
          <div class="gs-signatures">
            <div class="gs-sign-col">
              <div class="gs-sign-line">Class Teacher</div>
            </div>
            <div class="gs-sign-col">
              <div class="gs-sign-line">Exam Coordinator</div>
            </div>
            <div class="gs-sign-col">
              <div class="gs-sign-line">Headmaster / Principal</div>
            </div>
          </div>

          <div style="font-size: 0.7rem; color: #94a3b8; text-align: center; margin-top: 1.5rem;">
            Date of Issue: ${summary.generated_at} | System Generated by Sagarmatha EMS | Bhadrapur 2, Jhapa
          </div>
        </div>
      </div>

      <!-- Action Button Bar -->
      <div class="no-print" style="margin-top: 1.5rem; text-align: center; display: flex; justify-content: center; gap: 1rem;">
        <button class="btn btn-primary" onclick="window.print()">
          🖨️ Print Official Grade Sheet
        </button>
        <button class="btn btn-secondary" onclick="openStudentIdCard(${student.id})">
          🪪 View Student ID Card
        </button>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div style="color:red; text-align:center; padding: 2rem;">Failed to fetch grade sheet: ${err}</div>`;
  }
}

// Class Tabulation Sheet (लेजर)
async function loadClassTabulationLedger() {
  const examSel = document.getElementById('ledger-exam-select');
  const classSel = document.getElementById('ledger-class-select');
  const container = document.getElementById('tabulation-ledger-container');

  if (!examSel || !classSel || !container) return;

  const examId = examSel.value;
  const classId = classSel.value;

  if (!examId || !classId) {
    container.innerHTML = '<div style="padding: 2rem; text-align: center;">Please select an Exam and Class</div>';
    return;
  }

  container.innerHTML = '<div style="padding: 2rem; text-align: center;">Loading tabulation ledger...</div>';

  try {
    const res = await fetch(`/api/tabulation?exam_id=${examId}&class_id=${classId}`);
    const data = await res.json();

    const { class: cls, exam, subjects, students } = data;

    container.innerHTML = `
      <div style="margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 style="font-size: 1.2rem; font-weight: bold; color: #1e3a8a;">
            Tabulation Ledger: ${cls.name} - ${exam.name}
          </h3>
          <p style="font-size: 0.82rem; color: #64748b;">Total Students: ${students.length} | Official Record</p>
        </div>
        <div>
          <button class="btn btn-primary btn-sm no-print" onclick="window.print()">
            🖨️ Print Class Ledger
          </button>
        </div>
      </div>

      <div class="printable-area table-container">
        <table class="data-table" style="font-size: 0.8rem;">
          <thead>
            <tr>
              <th>Roll</th>
              <th>Reg No</th>
              <th>Student Name</th>
              <th>Sec</th>
              ${subjects.map(s => `<th>${s.code} (G)</th>`).join('')}
              <th>Total Marks</th>
              <th>GPA</th>
              <th>Status</th>
              <th>Rank</th>
            </tr>
          </thead>
          <tbody>
            ${students.map(st => `
              <tr>
                <td class="font-bold">${st.roll_no}</td>
                <td>${st.reg_no}</td>
                <td class="font-bold">${st.name}</td>
                <td>${st.section}</td>
                ${st.subject_evals.map(se => `
                  <td class="${se.grade === 'NG' ? 'text-danger font-bold' : ''}">
                    ${se.grade} (${se.gp})
                  </td>
                `).join('')}
                <td class="font-bold">${st.total_marks.toFixed(1)}</td>
                <td class="font-bold ${st.status === 'NG' ? 'text-danger' : 'text-success'}">
                  ${st.gpa_display}
                </td>
                <td>
                  <span class="badge ${st.status === 'PASS' ? 'badge-success' : 'badge-danger'}">
                    ${st.status}
                  </span>
                </td>
                <td class="font-bold">${st.rank ? `#${st.rank}` : '-'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div style="color: red; padding: 2rem;">Failed to load tabulation ledger.</div>`;
  }
}

function openStudentQuickGrade(studentId) {
  switchExamSubTab('gradesheet');
  const stSel = document.getElementById('gs-student-select');
  if (stSel) {
    stSel.value = studentId;
    generateOfficialGradeSheet();
  }
}

function generateStudentMarksheet(studentId) {
  switchView('exam', studentId);
}

// -------------------------------------------------------------
// Class Subjects Directory (विषय सूची)
// -------------------------------------------------------------
async function loadClassSubjectsDirectory() {
  const selectEl = document.getElementById('sub-dir-class-select');
  const container = document.getElementById('subject-directory-container');
  if (!container) return;

  if (!selectEl || !selectEl.value) {
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Please select a class to view its subjects.</div>';
    return;
  }

  const cid = selectEl.value;
  const currentClass = State.classes.find(c => String(c.id) === String(cid));
  const className = currentClass ? `${currentClass.name} (${currentClass.level})` : 'Selected Class';

  container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Loading curriculum subjects...</div>';

  try {
    const res = await fetch(`/api/subjects?class_id=${cid}`);
    const subjects = await res.json();

    if (!subjects || subjects.length === 0) {
      container.innerHTML = `
        <div style="padding: 2.5rem; text-align: center; background: #fff; border-radius: 8px; border: 1px dashed var(--border);">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">📖</div>
          <p style="font-weight: 600; color: #475569;">No subjects configured for ${className} yet.</p>
          <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem;">Add official Nepal CDC subjects for this class.</p>
          <button class="btn btn-primary btn-sm" onclick="openAddSubjectForClass(${cid})">+ Add Subject</button>
        </div>
      `;
      return;
    }

    const totalCH = subjects.reduce((sum, s) => sum + (Number(s.credit_hours) || 0), 0);
    const totalTh = subjects.reduce((sum, s) => sum + (Number(s.theory_full_marks) || 0), 0);
    const totalPr = subjects.reduce((sum, s) => sum + (Number(s.practical_full_marks) || 0), 0);

    container.innerHTML = `
      <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <h3 style="font-size: 1.15rem; font-weight: bold; color: #1e3a8a;">
            ${className} - Curriculum Subjects Directory (पाठ्यक्रम सूची)
          </h3>
          <p style="font-size: 0.82rem; color: #64748b;">
            Total Subjects: <strong>${subjects.length}</strong> | Total Credit Hours: <strong>${totalCH.toFixed(1)}</strong> | Total Full Marks: <strong>${totalTh + totalPr}</strong>
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-primary btn-sm" onclick="openAddSubjectForClass(${cid})">
            + Add Subject
          </button>
        </div>
      </div>

      <table class="data-table" style="font-size: 0.88rem;">
        <thead>
          <tr>
            <th style="width: 50px; text-align: center;">S.N.</th>
            <th style="width: 120px;">CDC Code</th>
            <th>Subject Name (English)</th>
            <th>विषय (नेपाली)</th>
            <th style="width: 100px; text-align: center;">Credit Hrs</th>
            <th style="width: 140px; text-align: center;">Theory (Full / Pass)</th>
            <th style="width: 140px; text-align: center;">Practical (Full / Pass)</th>
            <th style="width: 90px; text-align: center;">Total</th>
            <th style="width: 110px; text-align: center;">Type</th>
          </tr>
        </thead>
        <tbody>
          ${subjects.map((s, idx) => `
            <tr>
              <td style="font-weight: 600; text-align: center;">${idx + 1}</td>
              <td style="font-family: monospace; font-weight: bold; color: #0284c7;">${s.code}</td>
              <td style="font-weight: 600;">${s.name_en}</td>
              <td style="font-size: 0.95rem;">${s.name_np || '-'}</td>
              <td style="text-align: center; font-weight: bold;">${s.credit_hours}</td>
              <td style="text-align: center;">${s.theory_full_marks} / <span style="color: #64748b; font-weight: 500;">${s.theory_pass_marks}</span></td>
              <td style="text-align: center;">${s.practical_full_marks} / <span style="color: #64748b; font-weight: 500;">${s.practical_pass_marks}</span></td>
              <td style="text-align: center; font-weight: bold;">${s.theory_full_marks + s.practical_full_marks}</td>
              <td style="text-align: center;">
                <span class="badge ${s.is_optional ? 'badge-neutral' : 'badge-primary'}">
                  ${s.is_optional ? 'Optional' : 'Compulsory'}
                </span>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error('Failed to load class subjects directory:', err);
    container.innerHTML = '<div style="color: red; padding: 2rem;">Failed to load subjects directory.</div>';
  }
}

function openAddSubjectForClass(classId = null) {
  const sel = document.getElementById('new-subject-class-select');
  if (sel && classId) {
    sel.value = classId;
  }
  openModal('add-subject-modal');
}

async function handleCreateSubjectSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    class_id: parseInt(form.class_id.value),
    code: form.code.value.trim(),
    name_en: form.name_en.value.trim(),
    name_np: form.name_np.value.trim(),
    credit_hours: parseFloat(form.credit_hours.value || 4.0),
    theory_full_marks: parseFloat(form.theory_full_marks.value || 75.0),
    theory_pass_marks: parseFloat(form.theory_pass_marks.value || 27.0),
    practical_full_marks: parseFloat(form.practical_full_marks.value || 25.0),
    practical_pass_marks: parseFloat(form.practical_pass_marks.value || 10.0),
    is_optional: form.is_optional && form.is_optional.checked ? 1 : 0
  };

  try {
    const res = await apiFetch('/api/subjects', {
      method: 'POST',
      body: payload
    });
    const data = await res.json();
    if (data.success) {
      showToast('Curriculum subject added successfully!', 'success');
      closeModal('add-subject-modal');
      form.reset();
      
      // Refresh exam dropdown and subject directory
      const curExamClass = document.getElementById('exam-marks-class-select');
      if (curExamClass && String(curExamClass.value) === String(payload.class_id)) {
        await onExamClassChanged();
      }
      const dirClass = document.getElementById('sub-dir-class-select');
      if (dirClass) {
        dirClass.value = payload.class_id;
        await loadClassSubjectsDirectory();
      }
    } else {
      showToast(data.error || 'Failed to add subject', 'error');
    }
  } catch (err) {
    console.error('Error adding subject:', err);
    showToast('Failed to add subject', 'error');
  }
}

