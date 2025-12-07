let currentShiftId = null;

// Load shifts overview (metrics + mini-cards) with optional date filters
function loadShiftsOverview() {
    const startInput = document.getElementById('startDateInput');
    const endInput = document.getElementById('endDateInput');
    const params = new URLSearchParams();
    if (startInput && startInput.value) params.append('start_date', startInput.value);
    if (endInput && endInput.value) params.append('end_date', endInput.value);

    fetch('/get_shifts_overview?' + params.toString())
        .then(r => r.json())
        .then(data => {
            if (!data) {
                console.error('/get_shifts_overview returned no data');
                const mini = document.getElementById('shiftsMiniList');
                if (mini) mini.innerHTML = '<div class="alert alert-warning">لم يتم استلام بيانات الورديات</div>';
                return;
            }
            if (!data.success) {
                console.error('/get_shifts_overview error:', data.error || data);
                const mini = document.getElementById('shiftsMiniList');
                if (mini) mini.innerHTML = `<div class="alert alert-danger">خطأ في تحميل الورديات: ${data.error || 'unknown'}</div>`;
                return;
            }

            const totals = data.totals || {};
            const totalShifts = data.total_shifts || 0;
            document.getElementById('overviewTotalShifts').textContent = totalShifts;
            document.getElementById('overviewTotalSales').textContent = formatCurrency(totals.total_sales || 0);
            document.getElementById('overviewTotalExpenses').textContent = formatCurrency(totals.total_expenses || 0);
            document.getElementById('overviewOrdersCount').textContent = totals.orders_count || 0;
            document.getElementById('overviewProfit').textContent = formatCurrency(totals.estimated_profit || 0);

            const mini = document.getElementById('shiftsMiniList');
            if (!mini) return;
            if (!Array.isArray(data.shifts) || data.shifts.length === 0) {
                mini.innerHTML = '<div class="alert alert-info">لا توجد ورديات لعرضها</div>';
            } else {
                mini.innerHTML = data.shifts.map(s => `
                    <div class="shift-mini card p-2" style="min-width:200px;cursor:pointer" onclick="loadShiftDetails(${s.id})">
                        <div><strong>وردية ${s.id}</strong></div>
                        <div>الكاشير: ${s.cashier_name}</div>
                        <div>مبيعات: ${formatCurrency(s.total_sales)}</div>
                        <div>مصاريف: ${formatCurrency(s.total_expenses)}</div>
                        <div>طلبات: ${s.orders_count}</div>
                        <div>ربح: ${formatCurrency(s.estimated_profit)}</div>
                    </div>
                `).join('');
            }

            // Update download link to include date params
            const dl = document.getElementById('downloadReportLink');
            if (dl) dl.href = '/download_shifts_report?' + params.toString();
        })
        .catch(err => {
            console.error('Failed to load shifts overview', err);
            const mini = document.getElementById('shiftsMiniList');
            if (mini) mini.innerHTML = '<div class="alert alert-danger">خطأ في تحميل بيانات الورديات</div>';
        });
}

function handleFetchError(error) {
    console.error('Error:', error);
    alert('حدث خطأ أثناء تحميل البيانات');
}

// Update the date formatting function
function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    // Use Arabic locale and add seconds
    return date.toLocaleString('ar-EG', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Add helper functions at the top
function formatCurrency(amount) {
    return `${Number(amount).toFixed(2)} ج.م`;
}

function updateSummary(data) {
    const summaryFields = {
        'totalSales': data.total_sales,
        'totalExpenses': data.total_expenses,
        'totalReturns': data.total_returns,
        'totalInvoices': data.total_invoices,
        'cashAmount': data.cash_amount,
        'visaAmount': data.visa_amount,
        'ewalletAmount': data.ewallet_amount
    };

    Object.entries(summaryFields).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = formatCurrency(value);
        }
    });
    
    // Display cash boxes if available
    if (data.cash_boxes && Array.isArray(data.cash_boxes) && data.cash_boxes.length > 0) {
        const cashBoxesList = document.getElementById('cashBoxesList');
        const cashBoxesSection = document.getElementById('cashBoxesSummary');
        
        if (cashBoxesList && cashBoxesSection) {
            cashBoxesList.innerHTML = data.cash_boxes.map(box => `
                <div class="payment-item">
                    <span>${box.name}:</span>
                    <span>${formatCurrency(box.amount)}</span>
                </div>
            `).join('');
            cashBoxesSection.style.display = 'block';
        }
    } else {
        const cashBoxesSection = document.getElementById('cashBoxesSummary');
        if (cashBoxesSection) {
            cashBoxesSection.style.display = 'none';
        }
    }
}

function loadShiftDetails(shiftId) {
    const id = parseInt(shiftId, 10);
    if (isNaN(id)) {
        console.error('Invalid shift ID');
        return;
    }
    
    currentShiftId = id;
    fetch(`/get_shift_summary_shifts/${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            updateSummary(data);
            document.getElementById('shiftDetailsModal').style.display = 'block';
            showTab('sales');
        })
        .catch(handleFetchError);
}

function loadSales(shiftId) {
    fetch(`/get_shift_sales_shifts/${shiftId}`)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('salesList');
            if (!tbody) return;
            
            // Add null check for sales array and debug logging
            console.log('Sales data received:', data);
            
            if (!data.sales || !Array.isArray(data.sales)) {
                tbody.innerHTML = '<tr><td colspan="4">لا توجد مبيعات</td></tr>';
                return;
            }

            // Update the sales mapping in loadSales function
            tbody.innerHTML = data.sales.map(sale => {
                console.log('Processing sale:', sale); // Debug log
                return `
                    <tr onclick="showSaleDetails(${sale.id})" style="cursor: pointer;">
                        <td>${sale.sale_number || ''}</td>
                        <td>${formatDateTime(sale.created_at)}</td>
                        <td>${formatCurrency(sale.final_amount)}</td>
                        <td>${getPaymentMethodText(sale.payment_method)}</td>
                    </tr>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('Error loading sales:', error);
            const tbody = document.getElementById('salesList');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="4">خطأ في تحميل المبيعات</td></tr>';
            }
            handleFetchError(error);
        });
}

function getPaymentMethodText(method) {
    switch(method) {
        case 'cash':
            return 'نقدي';
        case 'visa':
            return 'فيزا';
        case 'ewallet':
            return 'محفظة إلكترونية';
        default:
            return method;
    }
}

function loadExpenses(shiftId) {
    fetch(`/get_shift_expenses_shifts/${shiftId}`)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('expensesList');
            if (!tbody) return;
            tbody.innerHTML = data.expenses.map(expense => `
                <tr>
                    <td>${expense.description || ''}</td>
                    <td>${formatCurrency(expense.amount)}</td>
                    <td>${formatDateTime(expense.created_at)}</td>
                </tr>
            `).join('');
        })
        .catch(handleFetchError);
}

function loadReturns(shiftId) {
    console.log('Loading returns for shift:', shiftId);
    const tbody = document.getElementById('returnsList');
    if (!tbody) {
        console.error('Returns table body not found');
        return;
    }

    fetch(`/get_shift_returns_shifts/${shiftId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Returns data:', data);
            if (!data.returns) {
                throw new Error('No returns data in response');
            }
            
            tbody.innerHTML = data.returns.map(return_ => `
                <tr onclick="showReturnDetails(${return_.id})">
                    <td>${return_.sale_number || ''}</td>
                    <td>${formatCurrency(return_.total_amount)}</td>
                    <td>${return_.reason || ''}</td>
                    <td>${formatDateTime(return_.created_at)}</td>
                </tr>
            `).join('');
        })
        .catch(error => {
            console.error('Error loading returns:', error);
            tbody.innerHTML = '<tr><td colspan="4">خطأ في تحميل المرتجعات</td></tr>';
            handleFetchError(error);
        });
}

function loadInvoices(shiftId) {
    console.log('Loading invoices for shift:', shiftId);
    const tbody = document.getElementById('invoicesList');
    if (!tbody) {
        console.error('Invoices table body not found');
        return;
    }

    fetch(`/get_shift_invoices_shifts/${shiftId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Invoices data:', data);
            if (!data.invoices) {
                throw new Error('No invoices data in response');
            }
            
            tbody.innerHTML = data.invoices.map(invoice => `
                <tr onclick="showInvoiceDetails(${invoice.id})">
                    <td>${invoice.invoice_number || ''}</td>
                    <td>${invoice.supplier_name || ''}</td>
                    <td>${formatCurrency(invoice.total_amount)}</td>
                    <td>${formatDateTime(invoice.created_at)}</td>
                </tr>
            `).join('');
        })
        .catch(error => {
            console.error('Error loading invoices:', error);
            tbody.innerHTML = '<tr><td colspan="4">خطأ في تحميل الفواتير</td></tr>';
            handleFetchError(error);
        });
}

function showTab(tabName) {
    console.log('Switching to tab:', tabName);

    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));

    // Remove active class from all buttons
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => btn.classList.remove('active'));

    // Show selected tab content
    const selectedTab = document.getElementById(`${tabName}Tab`);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activate selected button
    const selectedButton = document.querySelector(`.tab-btn[onclick*="${tabName}"]`);
    if (selectedButton) {
        selectedButton.classList.add('active');
    }

    // Load tab data
    if (currentShiftId) {
        switch(tabName) {
            case 'sales':
                loadSales(currentShiftId);
                break;
            case 'expenses':
                loadExpenses(currentShiftId);
                break;
            case 'returns':
                loadReturns(currentShiftId);
                break;
            case 'invoices':
                loadInvoices(currentShiftId);
                break;
        }
    }
}

function closeModal() {
    document.getElementById('shiftDetailsModal').style.display = 'none';
}

function showSaleDetails(saleId) {
    if (!saleId) {
        console.error('Invalid sale ID');
        return;
    }

    fetch(`/get_sale_details_shifts/${saleId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) {
                throw new Error('No data received');
            }
            showDetailModal('sale', data);
        })
        .catch(error => {
            console.error('Error loading sale details:', error);
            handleFetchError(error);
        });
}

function showReturnDetails(returnId) {
    fetch(`/get_return_details_shifts/${returnId}`)
        .then(response => response.json())
        .then(data => {
            showDetailModal('return', data);
        })
        .catch(handleFetchError);
}

function showInvoiceDetails(invoiceId) {
    fetch(`/get_invoice_details_shifts/${invoiceId}`)
        .then(response => response.json())
        .then(data => {
            showDetailModal('invoice', data);
        })
        .catch(handleFetchError);
}

function showDetailModal(type, data) {
    // Remove any existing modal
    const existingModal = document.querySelector('.detail-modal-backdrop');
    if (existingModal) {
        existingModal.remove();
    }

    const modalHTML = `
        <div class="detail-modal-backdrop" onclick="closeDetailModal()">
            <div class="detail-modal" onclick="event.stopPropagation()">
                <button class="close-btn" onclick="closeDetailModal()">&times;</button>
                <h3>${getModalTitle(type)}</h3>
                <div class="detail-content">
                    ${generateDetailContent(type, data)}
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

function closeDetailModal() {
    const modal = document.querySelector('.detail-modal-backdrop');
    if (modal) {
        modal.remove();
    }
}

function generateDetailContent(type, data) {
    switch(type) {
        case 'sale':
            return `
                <div class="sale-info">
                    <p>رقم الفاتورة: ${data.sale_number}</p>
                    <p>التوقيت: ${formatDateTime(data.created_at)}</p>
                    <p>العميل: ${data.customer_name || 'غير محدد'}</p>
                    <p>الهاتف: ${data.customer_phone || 'غير محدد'}</p>
                    <p>الإجمالي: ${formatCurrency(data.total_amount)}</p>
                    <p>الخصم: ${formatCurrency(data.discount_amount)}</p>
                    <p>الصافي: ${formatCurrency(data.final_amount)}</p>
                    <p>طريقة الدفع: ${getPaymentMethodText(data.payment_method)}</p>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>المنتج</th>
                            <th>الكمية</th>
                            <th>السعر</th>
                            <th>الإجمالي</th>
                            <th>المرتجع</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.items.map(item => `
                            <tr>
                                <td>${item.item_name}</td>
                                <td>${item.quantity}</td>
                                <td>${formatCurrency(item.unit_price)}</td>
                                <td>${formatCurrency(item.total_price)}</td>
                                <td>${item.returned_quantity || 0}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
        case 'return':
            return `
                <div class="return-info">
                    <p>رقم الفاتورة: ${data.sale_number}</p>
                    <p>التاريخ: ${formatDateTime(data.return_date)}</p>
                    <p>السبب: ${data.reason || ''}</p>
                    <p>الإجمالي: ${formatCurrency(data.total_amount)}</p>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>المنتج</th>
                            <th>الكمية</th>
                            <th>السعر</th>
                            <th>الإجمالي</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.items.map(item => `
                            <tr>
                                <td>${item.item_name}</td>
                                <td>${item.quantity}</td>
                                <td>${formatCurrency(item.unit_price)}</td>
                                <td>${formatCurrency(item.total_price)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
        case 'invoice':
            return `
                <div class="invoice-info">
                    <p>رقم الفاتورة: ${data.id}</p>
                    <p>التاريخ: ${formatDateTime(data.invoice_date)}</p>
                    <p>المورد: ${data.trader_name || ''}</p>
                    <p>الشركة: ${data.company_name || ''}</p>
                    <p>الإجمالي: ${formatCurrency(data.total_amount)}</p>
                    <p>المدفوع: ${formatCurrency(data.paid_amount)}</p>
                    <p>المتبقي: ${formatCurrency(data.remaining_amount)}</p>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>المنتج</th>
                            <th>الكمية</th>
                            <th>سعر الشراء</th>
                            <th>سعر البيع</th>
                            <th>الإجمالي</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.items.map(item => `
                            <tr>
                                <td>${item.item_name}</td>
                                <td>${item.quantity}</td>
                                <td>${formatCurrency(item.buy_price)}</td>
                                <td>${formatCurrency(item.sell_price)}</td>
                                <td>${formatCurrency(item.total_price)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
    }
}

function getModalTitle(type) {
    switch(type) {
        case 'sale':
            return 'تفاصيل المبيعات';
        case 'return':
            return 'تفاصيل المرتجعات';
        case 'invoice':
            return 'تفاصيل الفاتورة';
        default:
            return 'تفاصيل';
    }
}