// Cash Boxes Report JavaScript

document.addEventListener('DOMContentLoaded', function() {
    loadCashBoxes();
    loadTransactions();
    initializeDateFilters();
});

function initializeDateFilters() {
    const today = new Date();
    const endDate = today.toISOString().split('T')[0];
    const startDate = new Date(today.setDate(today.getDate() - 30)).toISOString().split('T')[0];
    
    document.getElementById('startDate').value = startDate;
    document.getElementById('endDate').value = endDate;
}

function loadCashBoxes() {
    console.log('Loading cash boxes...');
    fetch('/get_cash_box_summary')
        .then(response => {
            console.log('Response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Cash boxes data:', data);
            if (data.success) {
                displayCashBoxes(data.cash_boxes);
                populateCashBoxDropdowns(data.cash_boxes);
            } else {
                console.error('Error in response:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading cash boxes:', error);
        });
}

function displayCashBoxes(cashBoxes) {
    const container = document.getElementById('cashBoxesSummary');
    container.innerHTML = cashBoxes.map(box => `
        <div class="cash-box-card ${box.amount >= 0 ? 'positive' : 'negative'}">
            <div class="cash-box-header">
                <div class="cash-box-name">${box.name}</div>
                <div class="cash-box-icon">
                    <i class="fas fa-cash-register"></i>
                </div>
            </div>
            <div class="cash-box-balance">${formatCurrency(box.amount)}</div>
            <div class="balance-label">الرصيد الحالي</div>
        </div>
    `).join('');
}

function populateCashBoxDropdowns(cashBoxes) {
    const fromSelect = document.getElementById('fromCashBox');
    const toSelect = document.getElementById('toCashBox');
    const depositSelect = document.getElementById('depositCashBox');
    const withdrawSelect = document.getElementById('withdrawCashBox');
    const filterSelect = document.getElementById('filterCashBox');
    
    const options = cashBoxes.map(box => 
        `<option value="${box.id}">${box.name} (${formatCurrency(box.amount)})</option>`
    ).join('');
    
    fromSelect.innerHTML = '<option value="">اختر صندوق</option>' + options;
    toSelect.innerHTML = '<option value="">اختر صندوق</option>' + options;
    depositSelect.innerHTML = '<option value="">اختر صندوق</option>' + options;
    withdrawSelect.innerHTML = '<option value="">اختر صندوق</option>' + options;
    filterSelect.innerHTML += options;
}

function loadTransactions() {
    console.log('Loading transactions...');
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const cashBoxId = document.getElementById('filterCashBox').value;
    
    const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        ...(cashBoxId && { cash_box_id: cashBoxId })
    });
    
    console.log('Fetching with params:', params.toString());
    
    fetch(`/get_cash_box_transfers?${params}`)
        .then(response => {
            console.log('Transfers response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Transfers data:', data);
            if (data.success) {
                displayTransactions(data.transfers);
            } else {
                console.error('Error in response:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading transactions:', error);
        });
}

function displayTransactions(transactions) {
    const tbody = document.querySelector('#transactionsTable tbody');
    
    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">لا توجد حركات</td></tr>';
        return;
    }
    
    tbody.innerHTML = transactions.map(t => `
        <tr>
            <td>${new Date(t.transfer_date).toLocaleString('ar-EG')}</td>
            <td><span class="transaction-type ${t.transaction_type}">${getTransactionTypeLabel(t.transaction_type)}</span></td>
            <td>${t.from_cash_box_name || '-'}</td>
            <td>${t.to_cash_box_name || '-'}</td>
            <td>${formatCurrency(t.amount)}</td>
            <td>${t.notes || '-'}</td>
            <td>${t.user_name || '-'}</td>
        </tr>
    `).join('');
}

function getTransactionTypeLabel(type) {
    const labels = {
        'transfer': 'تحويل',
        'deposit': 'إيداع',
        'withdraw': 'سحب'
    };
    return labels[type] || type;
}

function formatCurrency(amount) {
    return parseFloat(amount || 0).toFixed(2) + ' ج.م';
}

// Transfer Modal
function showTransferModal() {
    document.getElementById('transferModal').classList.add('show');
}

function closeTransferModal() {
    document.getElementById('transferModal').classList.remove('show');
    clearTransferForm();
}

function clearTransferForm() {
    document.getElementById('fromCashBox').value = '';
    document.getElementById('toCashBox').value = '';
    document.getElementById('transferAmount').value = '';
    document.getElementById('transferNotes').value = '';
}

function processTransfer() {
    const fromCashBoxId = document.getElementById('fromCashBox').value;
    const toCashBoxId = document.getElementById('toCashBox').value;
    const amount = parseFloat(document.getElementById('transferAmount').value);
    const notes = document.getElementById('transferNotes').value;
    
    if (!fromCashBoxId || !toCashBoxId) {
        alert('الرجاء اختيار الصناديق');
        return;
    }
    
    if (fromCashBoxId === toCashBoxId) {
        alert('لا يمكن التحويل إلى نفس الصندوق');
        return;
    }
    
    if (!amount || amount <= 0) {
        alert('الرجاء إدخال مبلغ صحيح');
        return;
    }
    
    fetch('/transfer_cash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            from_cash_box_id: parseInt(fromCashBoxId),
            to_cash_box_id: parseInt(toCashBoxId),
            amount: amount,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('تم التحويل بنجاح');
            closeTransferModal();
            loadCashBoxes();
            loadTransactions();
        } else {
            alert(data.error || 'حدث خطأ أثناء التحويل');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ أثناء التحويل');
    });
}

// Deposit Modal
function showDepositModal() {
    document.getElementById('depositModal').classList.add('show');
}

function closeDepositModal() {
    document.getElementById('depositModal').classList.remove('show');
    clearDepositForm();
}

function clearDepositForm() {
    document.getElementById('depositCashBox').value = '';
    document.getElementById('depositAmount').value = '';
    document.getElementById('depositNotes').value = '';
}

function processDeposit() {
    const cashBoxId = document.getElementById('depositCashBox').value;
    const amount = parseFloat(document.getElementById('depositAmount').value);
    const notes = document.getElementById('depositNotes').value;
    
    if (!cashBoxId) {
        alert('الرجاء اختيار الصندوق');
        return;
    }
    
    if (!amount || amount <= 0) {
        alert('الرجاء إدخال مبلغ صحيح');
        return;
    }
    
    fetch('/deposit_cash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            cash_box_id: parseInt(cashBoxId),
            amount: amount,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('تم الإيداع بنجاح');
            closeDepositModal();
            loadCashBoxes();
            loadTransactions();
        } else {
            alert(data.error || 'حدث خطأ أثناء الإيداع');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ أثناء الإيداع');
    });
}

// Withdraw Modal
function showWithdrawModal() {
    document.getElementById('withdrawModal').classList.add('show');
}

function closeWithdrawModal() {
    document.getElementById('withdrawModal').classList.remove('show');
    clearWithdrawForm();
}

function clearWithdrawForm() {
    document.getElementById('withdrawCashBox').value = '';
    document.getElementById('withdrawAmount').value = '';
    document.getElementById('withdrawNotes').value = '';
}

function processWithdraw() {
    const cashBoxId = document.getElementById('withdrawCashBox').value;
    const amount = parseFloat(document.getElementById('withdrawAmount').value);
    const notes = document.getElementById('withdrawNotes').value;
    
    if (!cashBoxId) {
        alert('الرجاء اختيار الصندوق');
        return;
    }
    
    if (!amount || amount <= 0) {
        alert('الرجاء إدخال مبلغ صحيح');
        return;
    }
    
    fetch('/withdraw_cash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            cash_box_id: parseInt(cashBoxId),
            amount: amount,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('تم السحب بنجاح');
            closeWithdrawModal();
            loadCashBoxes();
            loadTransactions();
        } else {
            alert(data.error || 'حدث خطأ أثناء السحب');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('حدث خطأ أثناء السحب');
    });
}

// Close modals on outside click
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('show');
    }
}
