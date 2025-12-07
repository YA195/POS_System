// Employees Management JavaScript

let employees = [];
let currentEmployeeId = null;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    loadEmployees();
    setDefaultDateFilters();
    loadDisbursements();
});

// Set default date filters (first day of current month to today)
function setDefaultDateFilters() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    
    document.getElementById('filterStartDate').valueAsDate = firstDay;
    document.getElementById('filterEndDate').valueAsDate = today;
}

// Load Employees
async function loadEmployees() {
    try {
        const response = await fetch('/get_employees');
        employees = await response.json();
        
        displayEmployees();
        populateEmployeeFilters();
    } catch (error) {
        console.error('Error loading employees:', error);
        alert('حدث خطأ أثناء تحميل بيانات المناديب');
    }
}

// Display Employees in table
function displayEmployees() {
    const tbody = document.querySelector('#employeesTable tbody');
    tbody.innerHTML = '';
    
    employees.forEach(employee => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td data-label="الاسم">${employee.name}</td>
            <td data-label="الهاتف">${employee.phone || '-'}</td>
            <td data-label="المسمى الوظيفي">${employee.job_title || '-'}</td>
            <td data-label="الحالة">
                <span class="badge ${employee.is_active ? 'badge-success' : 'badge-danger'}">
                    ${employee.is_active ? 'نشط' : 'غير نشط'}
                </span>
            </td>
            <td data-label="تاريخ الإضافة">${employee.created_at || '-'}</td>
            <td data-label="الإجراءات">
                <div class="table-actions">
                    <button class="btn btn-warning btn-sm" onclick="editEmployee(${employee.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn ${employee.is_active ? 'btn-danger' : 'btn-success'} btn-sm" 
                            onclick="toggleEmployeeStatus(${employee.id}, ${!employee.is_active})">
                        <i class="fas fa-${employee.is_active ? 'ban' : 'check'}"></i>
                        ${employee.is_active ? 'تعطيل' : 'تفعيل'}
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Populate Employee Filters
function populateEmployeeFilters() {
    const filterSelect = document.getElementById('filterEmployee');
    const disbursementSelect = document.getElementById('disbursementEmployee');
    
    // Clear existing options except first
    filterSelect.innerHTML = '<option value="">الكل</option>';
    disbursementSelect.innerHTML = '<option value="">اختر موظف...</option>';
    
    // Add active employees only to disbursement select
    employees.forEach(employee => {
        // Filter dropdown (all employees)
        const filterOption = document.createElement('option');
        filterOption.value = employee.id;
        filterOption.textContent = employee.name;
        filterSelect.appendChild(filterOption);
        
        // Disbursement dropdown (active employees only)
        if (employee.is_active) {
            const disbOption = document.createElement('option');
            disbOption.value = employee.id;
            disbOption.textContent = employee.name;
            disbOption.dataset.name = employee.name;
            disbursementSelect.appendChild(disbOption);
        }
    });
}

// Show Add Employee Modal
function showAddEmployeeModal() {
    currentEmployeeId = null;
    document.getElementById('employeeModalTitle').textContent = 'إضافة مندوب جديد';
    document.getElementById('employeeForm').reset();
    document.getElementById('employeeId').value = '';
    document.getElementById('addEmployeeModal').style.display = 'block';
}

// Edit Employee
function editEmployee(id) {
    const employee = employees.find(e => e.id === id);
    if (!employee) return;
    
    currentEmployeeId = id;
    document.getElementById('employeeModalTitle').textContent = 'تعديل بيانات المندوب';
    document.getElementById('employeeId').value = id;
    document.getElementById('employeeName').value = employee.name;
    document.getElementById('employeePhone').value = employee.phone || '';
    document.getElementById('employeeJobTitle').value = employee.job_title || '';
    document.getElementById('addEmployeeModal').style.display = 'block';
}

// Close Employee Modal
function closeEmployeeModal() {
    document.getElementById('addEmployeeModal').style.display = 'none';
    document.getElementById('employeeForm').reset();
    currentEmployeeId = null;
}

// Save Employee
document.getElementById('employeeForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const data = {
        name: document.getElementById('employeeName').value,
        phone: document.getElementById('employeePhone').value,
        job_title: document.getElementById('employeeJobTitle').value
    };
    
    try {
        const employeeId = document.getElementById('employeeId').value;
        const url = employeeId ? `/update_employee/${employeeId}` : '/add_employee';
        const method = employeeId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success || result.id) {
            alert(employeeId ? 'تم تحديث البيانات بنجاح' : 'تم إضافة المندوب بنجاح');
            closeEmployeeModal();
            loadEmployees();
        } else {
            alert('حدث خطأ: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error saving employee:', error);
        alert('حدث خطأ أثناء حفظ البيانات');
    }
});

// Toggle Employee Status
async function toggleEmployeeStatus(id, newStatus) {
    const action = newStatus ? 'تفعيل' : 'تعطيل';
    if (!confirm(`هل أنت متأكد من ${action} هذا المندوب؟`)) return;
    
    try {
        const response = await fetch(`/toggle_employee_status/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: newStatus })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`تم ${action} المندوب بنجاح`);
            loadEmployees();
        } else {
            alert('حدث خطأ: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error toggling employee status:', error);
        alert('حدث خطأ أثناء تحديث الحالة');
    }
}

// Show Add Disbursement Modal
function showAddDisbursementModal() {
    document.getElementById('disbursementForm').reset();
    document.getElementById('addDisbursementModal').style.display = 'block';
}

// Close Disbursement Modal
function closeDisbursementModal() {
    document.getElementById('addDisbursementModal').style.display = 'none';
    document.getElementById('disbursementForm').reset();
}

// Save Disbursement
document.getElementById('disbursementForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const employeeSelect = document.getElementById('disbursementEmployee');
    const selectedOption = employeeSelect.options[employeeSelect.selectedIndex];
    
    const data = {
        employee_id: employeeSelect.value,
        employee_name: selectedOption.dataset.name,
        amount: parseFloat(document.getElementById('disbursementAmount').value),
        notes: document.getElementById('disbursementNotes').value
    };
    
    try {
        const response = await fetch('/add_disbursement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success || result.id) {
            alert('تم صرف المبلغ بنجاح');
            closeDisbursementModal();
            loadDisbursements();
        } else {
            alert('حدث خطأ: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error saving disbursement:', error);
        alert('حدث خطأ أثناء حفظ البيانات');
    }
});

// Load Disbursements
async function loadDisbursements() {
    await loadDisbursementSummary();
}

// Load Disbursement Summary
async function loadDisbursementSummary() {
    try {
        const startDate = document.getElementById('filterStartDate').value;
        const endDate = document.getElementById('filterEndDate').value;
        const employeeId = document.getElementById('filterEmployee').value;
        
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        const response = await fetch(`/get_employee_disbursement_summary?${params}`);
        const summary = await response.json();
        
        displayDisbursementSummary(summary, employeeId);
    } catch (error) {
        console.error('Error loading disbursement summary:', error);
        alert('حدث خطأ أثناء تحميل ملخص الصرف');
    }
}

// Display Disbursement Summary
function displayDisbursementSummary(summary, filterEmployeeId) {
    const tbody = document.querySelector('#summaryTable tbody');
    tbody.innerHTML = '';
    
    // Filter by employee if selected
    let filteredSummary = summary;
    if (filterEmployeeId) {
        filteredSummary = summary.filter(s => s.employee_id == filterEmployeeId);
    }
    
    if (filteredSummary.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">لا توجد بيانات</td></tr>';
        return;
    }
    
    filteredSummary.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'employee-row';
        row.dataset.employeeId = item.employee_id;
        row.innerHTML = `
            <td data-label="الموظف">
                <i class="fas fa-chevron-left expand-icon" id="icon-${item.employee_id}"></i>
                ${item.employee_name}
            </td>
            <td data-label="الهاتف">${item.phone || '-'}</td>
            <td data-label="المسمى الوظيفي">${item.job_title || '-'}</td>
            <td data-label="إجمالي المبلغ" style="font-weight: bold; color: #28a745;">${item.total_amount.toFixed(2)} ج.م</td>
            <td data-label="عدد المرات">${item.disbursement_count}</td>
            <td data-label="التفاصيل">
                <div class="table-actions">
                    <button class="btn btn-info btn-sm" onclick="showDisbursementDetails(${item.employee_id}, '${item.employee_name}')">
                        <i class="fas fa-eye"></i> التفاصيل
                    </button>
                </div>
            </td>
        `;
        
        row.addEventListener('click', function(e) {
            // Don't expand if clicking on button
            if (e.target.closest('button')) return;
            toggleEmployeeDetails(item.employee_id);
        });
        
        tbody.appendChild(row);
        
        // Add details row (hidden initially)
        const detailsRow = document.createElement('tr');
        detailsRow.className = 'details-row';
        detailsRow.id = `details-${item.employee_id}`;
        detailsRow.innerHTML = `
            <td colspan="6" class="details-cell" data-label="التفاصيل">
                <div class="details-content" id="content-${item.employee_id}">
                    <p style="text-align: center; color: #6c757d;">جاري التحميل...</p>
                </div>
            </td>
        `;
        tbody.appendChild(detailsRow);
    });
}

// Toggle Employee Details
async function toggleEmployeeDetails(employeeId) {
    const detailsRow = document.getElementById(`details-${employeeId}`);
    const icon = document.getElementById(`icon-${employeeId}`);
    const content = document.getElementById(`content-${employeeId}`);
    
    if (detailsRow.classList.contains('expanded')) {
        // Collapse
        detailsRow.classList.remove('expanded');
        icon.classList.remove('expanded');
    } else {
        // Expand and load details
        detailsRow.classList.add('expanded');
        icon.classList.add('expanded');
        
        // Load disbursement details
        await loadEmployeeDisbursementDetails(employeeId, content);
    }
}

// Load Employee Disbursement Details
async function loadEmployeeDisbursementDetails(employeeId, container) {
    try {
        const startDate = document.getElementById('filterStartDate').value;
        const endDate = document.getElementById('filterEndDate').value;
        
        const params = new URLSearchParams();
        params.append('employee_id', employeeId);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        const response = await fetch(`/get_disbursements?${params}`);
        const disbursements = await response.json();
        
        if (disbursements.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #6c757d;">لا توجد عمليات صرف في هذه الفترة</p>';
            return;
        }
        
        let html = `
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>التاريخ والوقت</th>
                        <th>المبلغ</th>
                        <th>الملاحظات</th>
                        <th>تم الصرف بواسطة</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        disbursements.forEach(d => {
            html += `
                <tr>
                    <td data-label="التاريخ والوقت">${new Date(d.disbursement_date).toLocaleString('ar-EG')}</td>
                    <td data-label="المبلغ" style="color: #28a745; font-weight: bold;">${d.amount.toFixed(2)} ج.م</td>
                    <td data-label="الملاحظات">${d.notes || '-'}</td>
                    <td data-label="تم الصرف بواسطة">${d.given_by}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading disbursement details:', error);
        container.innerHTML = '<p style="text-align: center; color: #dc3545;">حدث خطأ أثناء تحميل التفاصيل</p>';
    }
}

// Show Disbursement Details in Modal
async function showDisbursementDetails(employeeId, employeeName) {
    document.getElementById('detailsEmployeeName').textContent = `تفاصيل الصرف - ${employeeName}`;
    document.getElementById('disbursementDetailsModal').style.display = 'block';
    
    const tbody = document.querySelector('#detailsTable tbody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">جاري التحميل...</td></tr>';
    
    try {
        const startDate = document.getElementById('filterStartDate').value;
        const endDate = document.getElementById('filterEndDate').value;
        
        const params = new URLSearchParams();
        params.append('employee_id', employeeId);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        
        const response = await fetch(`/get_disbursements?${params}`);
        const disbursements = await response.json();
        
        tbody.innerHTML = '';
        
        if (disbursements.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">لا توجد عمليات صرف في هذه الفترة</td></tr>';
            return;
        }
        
        disbursements.forEach(d => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td data-label="التاريخ والوقت">${new Date(d.disbursement_date).toLocaleString('ar-EG')}</td>
                <td data-label="المبلغ" style="color: #28a745; font-weight: bold;">${d.amount.toFixed(2)} ج.م</td>
                <td data-label="الملاحظات">${d.notes || '-'}</td>
                <td data-label="تم الصرف بواسطة">${d.given_by}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading disbursement details:', error);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #dc3545;">حدث خطأ أثناء تحميل التفاصيل</td></tr>';
    }
}

// Close Disbursement Details Modal
function closeDisbursementDetailsModal() {
    document.getElementById('disbursementDetailsModal').style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const employeeModal = document.getElementById('addEmployeeModal');
    const disbursementModal = document.getElementById('addDisbursementModal');
    const detailsModal = document.getElementById('disbursementDetailsModal');
    
    if (event.target == employeeModal) {
        closeEmployeeModal();
    }
    if (event.target == disbursementModal) {
        closeDisbursementModal();
    }
    if (event.target == detailsModal) {
        closeDisbursementDetailsModal();
    }
}
