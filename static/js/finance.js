/**
 * finance.js - Finance & Fee Management for Sagarmatha EMS
 * Covers student billing, fee collection counter, printable receipts, and expense tracking.
 */

let financeState = {
  invoices: [],
  expenses: [],
  summary: null,
  activeTab: 'invoices'
};

async function loadFinanceView() {
  switchFinanceSubTab('invoices');
  await fetchFinanceSummary();
}

function switchFinanceSubTab(tabName) {
  financeState.activeTab = tabName;
  document.querySelectorAll('.fin-tab-btn').forEach(b => {
    if (b.dataset.tab === tabName) b.classList.add('active');
    else b.classList.remove('active');
  });

  document.querySelectorAll('.finance-sub-panel').forEach(p => p.style.display = 'none');
  const target = document.getElementById(`finance-sub-${tabName}`);
  if (target) target.style.display = 'block';

  if (tabName === 'invoices') loadInvoicesList();
  if (tabName === 'collect') prepareFeeCollectionWindow();
  if (tabName === 'expenses') loadExpensesList();
  if (tabName === 'structure') loadFeeStructures();
}

async function fetchFinanceSummary() {
  try {
    const res = await fetch('/api/finance/summary');
    const data = await res.json();
    financeState.summary = data;

    const elColl = document.getElementById('fin-metric-collected');
    if (elColl) elColl.textContent = `NPR ${Number(data.total_collected).toLocaleString()}`;

    const elDue = document.getElementById('fin-metric-due');
    if (elDue) elDue.textContent = `NPR ${Number(data.total_due).toLocaleString()}`;

    const elExp = document.getElementById('fin-metric-expense');
    if (elExp) elExp.textContent = `NPR ${Number(data.total_expenses).toLocaleString()}`;

    const elNet = document.getElementById('fin-metric-net');
    if (elNet) {
      elNet.textContent = `NPR ${Number(data.net_cashflow).toLocaleString()}`;
      elNet.style.color = data.net_cashflow >= 0 ? '#15803d' : '#dc2626';
    }
  } catch (err) {
    console.error('Failed to load finance summary:', err);
  }
}

async function loadInvoicesList() {
  const cidSel = document.getElementById('fin-filter-class');
  const statusSel = document.getElementById('fin-filter-status');
  const tbody = document.getElementById('finance-invoices-tbody');

  const cid = cidSel ? cidSel.value : '';
  const status = statusSel ? statusSel.value : '';

  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem;">Loading billing invoices...</td></tr>';
  }

  try {
    const res = await fetch(`/api/finance/invoices?class_id=${cid}&status=${status}`);
    const invoices = await res.json();
    financeState.invoices = invoices;

    if (invoices.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding: 2rem; color: #64748b;">No bills found for the selected filter.</td></tr>';
      return;
    }

    tbody.innerHTML = invoices.map(inv => {
      const netPayable = inv.total_amount + inv.fine - inv.discount;
      const dueRemaining = Math.max(0, netPayable - inv.paid_amount);
      const statusBadge = inv.status === 'Paid' ? 'badge-success' : (inv.status === 'Partially Paid' ? 'badge-warning' : 'badge-danger');

      return `
        <tr>
          <td class="font-bold">${inv.invoice_no}</td>
          <td>
            <div style="font-weight: 700;">${inv.first_name} ${inv.last_name}</div>
            <div style="font-size: 0.78rem; color: #64748b;">Roll ${inv.roll_no} (${inv.reg_no})</div>
          </td>
          <td><span class="badge badge-info">${inv.class_name}</span></td>
          <td>${inv.month} ${inv.year}</td>
          <td class="font-bold">NPR ${Number(netPayable).toLocaleString()}</td>
          <td class="text-success font-bold">NPR ${Number(inv.paid_amount).toLocaleString()}</td>
          <td class="text-danger font-bold">NPR ${Number(dueRemaining).toLocaleString()}</td>
          <td><span class="badge ${statusBadge}">${inv.status}</span></td>
          <td>
            <div style="display: flex; gap: 0.35rem;">
              ${dueRemaining > 0 ? `
                <button class="btn btn-primary btn-sm" onclick="quickCollectPayment(${inv.id})">
                  💳 Pay
                </button>
              ` : `
                <button class="btn btn-secondary btn-sm" onclick="viewInvoiceReceipts(${inv.id})">
                  🧾 Receipt
                </button>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Failed to load invoices.</td></tr>';
  }
}

// Fee Collection Window
async function prepareFeeCollectionWindow() {
  const classSel = document.getElementById('collect-fee-class-select');
  const invoiceSel = document.getElementById('collect-fee-invoice-select');
  if (!classSel || !invoiceSel) return;

  const cid = classSel.value;
  if (!cid) {
    invoiceSel.innerHTML = '<option value="">-- Select Class First --</option>';
    return;
  }

  try {
    const res = await fetch(`/api/finance/invoices?class_id=${cid}&status=Unpaid`);
    const unpaid = await res.json();

    const resPart = await fetch(`/api/finance/invoices?class_id=${cid}&status=Partially Paid`);
    const part = await resPart.json();

    const allPending = [...unpaid, ...part];

    if (allPending.length === 0) {
      invoiceSel.innerHTML = '<option value="">All students in this class have settled fees!</option>';
      return;
    }

    invoiceSel.innerHTML = '<option value="">-- Choose Student Bill --</option>' + allPending.map(inv => {
      const net = inv.total_amount + inv.fine - inv.discount;
      const due = net - inv.paid_amount;
      return `<option value="${inv.id}" data-due="${due}" data-student="${inv.first_name} ${inv.last_name}">
        ${inv.first_name} ${inv.last_name} (Roll ${inv.roll_no}) - ${inv.month} | Due: NPR ${due}
      </option>`;
    }).join('');
  } catch (err) {
    invoiceSel.innerHTML = '<option value="">Error loading invoices</option>';
  }
}

function onInvoiceSelectedForPayment() {
  const sel = document.getElementById('collect-fee-invoice-select');
  const opt = sel.options[sel.selectedIndex];
  if (!opt || !opt.dataset.due) return;

  const due = parseFloat(opt.dataset.due);
  document.getElementById('collect-fee-amount').value = due;
  document.getElementById('collect-fee-due-display').textContent = `NPR ${due.toLocaleString()}`;
}

function quickCollectPayment(invoiceId) {
  switchFinanceSubTab('collect');
  setTimeout(() => {
    const inv = financeState.invoices.find(i => i.id === invoiceId);
    if (inv) {
      const classSel = document.getElementById('collect-fee-class-select');
      if (classSel) classSel.value = inv.class_id;
      prepareFeeCollectionWindow().then(() => {
        const invSel = document.getElementById('collect-fee-invoice-select');
        if (invSel) {
          invSel.value = invoiceId;
          onInvoiceSelectedForPayment();
        }
      });
    }
  }, 100);
}

// Payment Submission
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('collect-fee-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        invoice_id: form.invoice_id.value,
        amount_paid: parseFloat(form.amount_paid.value),
        discount: parseFloat(form.discount.value || 0),
        fine: parseFloat(form.fine.value || 0),
        payment_mode: form.payment_mode.value,
        transaction_ref: form.transaction_ref.value.trim(),
        received_by: form.received_by.value.trim() || 'Accountant',
        notes: form.notes.value.trim()
      };

      try {
        const res = await fetch('/api/finance/pay', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Payment collected! Receipt: ${data.receipt_no}`, 'success');
          form.reset();
          fetchFinanceSummary();
          fetchSchoolInfo();
          // Open printable receipt immediately!
          viewPrintableReceipt(data.receipt_no);
        } else {
          showToast(data.error || 'Failed to collect payment', 'error');
        }
      } catch (err) {
        showToast('Error communicating with server', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Generate Invoices Form
  const genForm = document.getElementById('generate-invoices-form');
  if (genForm) {
    genForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = genForm.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        class_id: genForm.class_id.value,
        month: genForm.month.value,
        year: genForm.year.value
      };

      try {
        const res = await fetch('/api/finance/invoices/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          closeModal('generate-invoices-modal');
          loadInvoicesList();
          fetchFinanceSummary();
        } else {
          showToast(data.error || 'Failed to generate bills', 'error');
        }
      } catch (err) {
        showToast('Error generating bills', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Expense Form
  const expForm = document.getElementById('add-expense-form');
  if (expForm) {
    expForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = expForm.querySelector('button[type="submit"]');
      btn.disabled = true;

      const payload = {
        title: expForm.title.value.trim(),
        category: expForm.category.value,
        amount: parseFloat(expForm.amount.value),
        payment_mode: expForm.payment_mode.value,
        paid_to: expForm.paid_to.value.trim(),
        approved_by: expForm.approved_by.value.trim() || 'Principal',
        notes: expForm.notes.value.trim()
      };

      try {
        const res = await fetch('/api/finance/expenses', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast('Expense recorded successfully!', 'success');
          closeModal('add-expense-modal');
          expForm.reset();
          loadExpensesList();
          fetchFinanceSummary();
        } else {
          showToast(data.error || 'Failed to record expense', 'error');
        }
      } catch (err) {
        showToast('Error recording expense', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  }
});

// Official Printable Fee Receipt (रसिद / भौचर)
async function viewPrintableReceipt(receiptNo) {
  try {
    const res = await fetch(`/api/finance/receipt/${receiptNo}`);
    const data = await res.json();
    if (data.error) {
      showToast(data.error, 'error');
      return;
    }

    const { school, items, due_remaining } = data;
    const modalBody = document.getElementById('receipt-modal-body');
    if (!modalBody) return;

    modalBody.innerHTML = `
      <div class="printable-area">
        <div class="receipt-container">
          <!-- School Header -->
          <div class="receipt-header">
            <div style="font-size: 0.8rem; color: #475569; font-weight: 600;">नेपाल सरकार | शिक्षा तथा खेलकुद शाखा</div>
            <h2>${school.name_en}</h2>
            <div style="font-size: 0.95rem; font-weight: bold; color: #0f766e;">${school.name_np}</div>
            <p>${school.address_en} | Phone: ${school.phone}</p>
            <div class="receipt-badge-title">OFFICIAL FEE RECEIPT / शुल्क रसिद</div>
          </div>

          <!-- Receipt Details Meta -->
          <div class="receipt-meta-grid">
            <div><strong>Receipt No:</strong> <span style="font-family: monospace; font-size: 1rem; color: #0f766e;">${data.receipt_no}</span></div>
            <div><strong>Date:</strong> ${data.payment_date} (B.S. 2081)</div>
            <div><strong>Student Name:</strong> ${data.first_name} ${data.last_name} (${data.name_np || ''})</div>
            <div><strong>Class / Section:</strong> ${data.class_name} (${data.section_name})</div>
            <div><strong>Reg / Roll No:</strong> ${data.reg_no} / Roll: ${data.roll_no}</div>
            <div><strong>Billing Month:</strong> ${data.month} ${data.year}</div>
            <div><strong>Payment Mode:</strong> ${data.payment_mode} ${data.transaction_ref ? `(${data.transaction_ref})` : ''}</div>
            <div><strong>Guardian:</strong> ${data.guardian_name} (${data.guardian_phone})</div>
          </div>

          <!-- Items Breakdown -->
          <table class="receipt-items-table">
            <thead>
              <tr>
                <th style="width: 40px;">S.N.</th>
                <th>Fee Description / Particulars</th>
                <th style="text-align: right; width: 120px;">Amount (NPR)</th>
              </tr>
            </thead>
            <tbody>
              ${items && items.length > 0 ? items.map((it, idx) => `
                <tr>
                  <td style="text-align: center;">${idx + 1}</td>
                  <td>${it.fee_head_name}</td>
                  <td style="text-align: right;">${Number(it.amount).toLocaleString()}</td>
                </tr>
              `).join('') : `
                <tr><td colspan="3" style="text-align:center;">General Tuition & Examination Fees</td></tr>
              `}
              <tr class="receipt-total-row">
                <td colspan="2" style="text-align: right;">Total Bill:</td>
                <td style="text-align: right;">NPR ${Number(data.total_amount).toLocaleString()}</td>
              </tr>
              ${data.discount > 0 ? `
                <tr>
                  <td colspan="2" style="text-align: right; color: green;">Scholarship / Discount:</td>
                  <td style="text-align: right; color: green;">- NPR ${Number(data.discount).toLocaleString()}</td>
                </tr>
              ` : ''}
              <tr class="receipt-total-row" style="background: #f0fdfa; color: #0f766e; font-size: 0.95rem;">
                <td colspan="2" style="text-align: right;">Amount Paid (Now):</td>
                <td style="text-align: right; font-weight: bold;">NPR ${Number(data.amount_paid).toLocaleString()}</td>
              </tr>
              <tr style="font-weight: bold;">
                <td colspan="2" style="text-align: right; color: ${due_remaining > 0 ? '#dc2626' : '#15803d'};">Remaining Due:</td>
                <td style="text-align: right; color: ${due_remaining > 0 ? '#dc2626' : '#15803d'};">NPR ${Number(due_remaining).toLocaleString()}</td>
              </tr>
            </tbody>
          </table>

          <div style="font-size: 0.8rem; font-style: italic; color: #475569; margin-bottom: 1.5rem;">
            Note: Fees once paid are non-refundable. Please preserve this receipt for future reference.
          </div>

          <!-- Signatures -->
          <div class="receipt-signatures">
            <div class="receipt-sign-col">
              <div class="line">Parent / Depositor</div>
            </div>
            <div class="receipt-sign-col">
              <div class="line">Authorized Signature<br>(${data.received_by})</div>
            </div>
          </div>
        </div>
      </div>

      <div class="no-print" style="margin-top: 1.5rem; text-align: center; display: flex; justify-content: center; gap: 1rem;">
        <button class="btn btn-primary" onclick="window.print()">
          🖨️ Print Fee Receipt
        </button>
        <button class="btn btn-secondary" onclick="closeModal('receipt-modal')">
          Close
        </button>
      </div>
    `;

    openModal('receipt-modal');
  } catch (err) {
    showToast('Failed to load receipt', 'error');
  }
}

async function viewInvoiceReceipts(invoiceId) {
  try {
    const inv = financeState.invoices.find(i => i.id === invoiceId);
    if (!inv) return;

    const res = await fetch(`/api/finance/summary`);
    const data = await res.json();
    // Find receipt matching this invoice or student
    const match = data.recent_payments.find(p => p.receipt_no.includes(String(invoiceId)) || p.first_name === inv.first_name);
    if (match) {
      viewPrintableReceipt(match.receipt_no);
    } else {
      // Fallback
      viewPrintableReceipt(`REC-2081-${invoiceId}`);
    }
  } catch (err) {
    showToast('Could not load receipt for this bill', 'error');
  }
}

// Expenses List
async function loadExpensesList() {
  const tbody = document.getElementById('finance-expenses-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading school expenses...</td></tr>';

  try {
    const res = await fetch('/api/finance/expenses');
    const expenses = await res.json();
    financeState.expenses = expenses;

    if (expenses.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No expenses recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = expenses.map(e => `
      <tr>
        <td class="font-bold">${e.expense_date}</td>
        <td class="font-bold">${e.title}</td>
        <td><span class="badge badge-info">${e.category}</span></td>
        <td class="font-bold text-danger">NPR ${Number(e.amount).toLocaleString()}</td>
        <td>${e.paid_to}</td>
        <td>${e.approved_by}</td>
        <td><span class="badge badge-neutral">${e.payment_mode}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load expenses.</td></tr>';
  }
}

// Fee Structure List
async function loadFeeStructures() {
  const container = document.getElementById('finance-structures-container');
  if (!container) return;

  try {
    const res = await fetch('/api/finance/structure');
    const items = await res.json();

    // Group by class
    const byClass = {};
    items.forEach(it => {
      if (!byClass[it.class_name]) byClass[it.class_name] = [];
      byClass[it.class_name].push(it);
    });

    container.innerHTML = Object.entries(byClass).map(([cname, feeList]) => {
      const tot = feeList.reduce((acc, f) => acc + f.amount, 0);
      return `
        <div class="feature-card" style="margin-bottom: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h4 style="font-size: 1.1rem; font-weight: bold; color: #1e3a8a;">${cname}</h4>
            <span class="badge badge-success">Total Monthly: NPR ${Number(tot).toLocaleString()}</span>
          </div>
          <table class="data-table" style="font-size: 0.85rem;">
            <thead>
              <tr><th>Fee Head</th><th>Type</th><th style="text-align: right;">Amount (NPR)</th></tr>
            </thead>
            <tbody>
              ${feeList.map(f => `
                <tr>
                  <td>${f.fee_head_name}</td>
                  <td><span class="badge badge-neutral">${f.is_recurring ? 'Monthly' : 'One-time'}</span></td>
                  <td style="text-align: right; font-weight: bold;">${Number(f.amount).toLocaleString()}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }).join('');

  } catch (err) {
    container.innerHTML = '<div style="color: red;">Failed to load fee structures.</div>';
  }
}
