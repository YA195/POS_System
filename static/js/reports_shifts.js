document.addEventListener('DOMContentLoaded', function() {
    const runBtn = document.getElementById('runReportBtn');
    if (runBtn) runBtn.addEventListener('click', runReport);

    // wire presets
    const preset7 = document.getElementById('preset7');
    const presetToday = document.getElementById('presetToday');
    const presetMonth = document.getElementById('presetMonth');
    if (preset7) preset7.addEventListener('click', () => applyPreset(7));
    if (presetToday) presetToday.addEventListener('click', () => applyPreset(1));
    if (presetMonth) presetMonth.addEventListener('click', () => applyMonthPreset());

    // default the date range to the last 7 days
    const startInput = document.getElementById('reportStart');
    const endInput = document.getElementById('reportEnd');
    if (startInput && endInput) {
        const now = new Date();
        const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const start = new Date(end);
        start.setDate(end.getDate() - 6);
        function toIsoDate(d){ return d.toISOString().slice(0,10); }
        startInput.value = toIsoDate(start);
        endInput.value = toIsoDate(end);
        // auto-run the report once defaults are set
        setTimeout(runReport, 100);

        // auto-run on date change with debounce
        let debounceTimer = null;
        [startInput, endInput].forEach(inp => {
            inp.addEventListener('change', () => {
                if (debounceTimer) clearTimeout(debounceTimer);
                debounceTimer = setTimeout(runReport, 400);
            });
        });
    }
});

function formatCurrency(amount) {
    return Number(amount || 0).toFixed(2) + ' ج.م';
}

let lastData = null;

function renderShifts(data) {
    const shiftsList = document.getElementById('shiftsList');
    shiftsList.innerHTML = '';
    if (window.innerWidth > 768) {
        // render table with separate column for total cash boxes sum
        const table = document.createElement('table');
        table.className = 'data-table';
        table.innerHTML = `<thead><tr><th>رقم الوردية</th><th>الكاشير</th><th>وقت البدء</th><th>وقت النهاية</th><th>طلبات</th><th>مبيعات</th><th>الربح</th><th>خصم</th><th>مجموع الصناديق</th><th>تفاصيل الصناديق</th><th>تفاصيل</th></tr></thead><tbody>` + data.shifts_list.map(s => {
            // Calculate total sum of cash boxes
            const cashBoxesSum = s.cash_boxes && s.cash_boxes.length > 0 
                ? s.cash_boxes.reduce((sum, cb) => sum + (cb.amount || 0), 0) 
                : 0;
            
            return `
<tr>
<td>${s.id}</td>
<td>${s.cashier_name || ''}</td>
<td>${s.start_time ? new Date(s.start_time).toLocaleString('ar-EG') : ''}</td>
<td>${s.end_time ? new Date(s.end_time).toLocaleString('ar-EG') : ''}</td>
<td>${s.orders_count}</td>
<td>${formatCurrency(s.orders_total)}</td>
<td>${formatCurrency(s.profit)}</td>
<td>${formatCurrency(s.discount_amount)}</td>
<td>${formatCurrency(cashBoxesSum)}</td>
<td>${s.cash_boxes && s.cash_boxes.length > 0 ? s.cash_boxes.map(cb => `${cb.name}: ${formatCurrency(cb.amount)}`).join('<br>') : '-'}</td>
<td><button class="btn btn-sm btn-outline-secondary" onclick="showShiftDetails(event, ${s.id})">تفاصيل</button></td>
</tr>
`;
        }).join('') + `</tbody>`;
        shiftsList.appendChild(table);
    } else {
        // render cards
        const listHtml = data.shifts_list.map(s => {
            const cashBoxesSum = s.cash_boxes && s.cash_boxes.length > 0 
                ? s.cash_boxes.reduce((sum, cb) => sum + (cb.amount || 0), 0) 
                : 0;
            
            return `
            <div class="shift-card" data-id="${s.id}">
                <div class="left">
                    <div><strong>وردية ${s.id}</strong> — ${s.cashier_name || ''}</div>
                    <div class="meta">${s.start_time ? new Date(s.start_time).toLocaleString('ar-EG') : ''} — ${s.end_time ? new Date(s.end_time).toLocaleString('ar-EG') : ''}</div>
                </div>
                <div class="right">
                    <div>طلبات: <strong>${s.orders_count}</strong></div>
                    <div>مبيعات: <strong>${formatCurrency(s.orders_total)}</strong></div>
                    <div>الربح: <strong>${formatCurrency(s.profit)}</strong></div>
                    <div>خصم: <strong>${formatCurrency(s.discount_amount)}</strong></div>
                    <div>مجموع الصناديق: <strong>${formatCurrency(cashBoxesSum)}</strong></div>
                    ${s.cash_boxes && s.cash_boxes.length > 0 ? '<div>تفاصيل الصناديق: <strong>' + s.cash_boxes.map(cb => `${cb.name}: ${formatCurrency(cb.amount)}`).join(', ') + '</strong></div>' : ''}
                    <div class="mt-1"><button class="btn btn-sm btn-outline-secondary" onclick="showShiftDetails(event, ${s.id})">تفاصيل</button></div>
                </div>
            </div>
`;
        }).join('');
        shiftsList.insertAdjacentHTML('beforeend', listHtml);
    }
}

async function runReport() {
    const start = document.getElementById('reportStart').value;
    const end = document.getElementById('reportEnd').value;
    showLoading(true);
    clearError();

    const params = new URLSearchParams();
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);

    try {
        const res = await fetch('/api/reports_shifts_data?' + params.toString());
        const data = await res.json();
        if (!data.success) {
            showError('خطأ في جلب التقرير: ' + (data.error || 'unknown'));
            return;
        }

        lastData = data;

        document.getElementById('metricSales').textContent = formatCurrency(data.sales.total_sales);
        document.getElementById('metricExpenses').textContent = formatCurrency(data.shifts.total_expenses + (data.sales.delivery_fees || 0));
        document.getElementById('metricReturns').textContent = formatCurrency(data.returns.total_returns);
        document.getElementById('metricOrders').textContent = (data.sales.orders_count || 0);
        document.getElementById('metricInvoices').textContent = formatCurrency(data.invoices.total_invoices || 0);
        document.getElementById('metricProfit').textContent = formatCurrency(data.estimated_profit || 0);
        document.getElementById('metricDiscounts').textContent = formatCurrency(data.discount_total || 0);

        // Calculate total cash boxes amounts
        let cashBoxesTotal = {};
        let cashBoxesGrandTotal = 0;
        if (data.shifts_list) {
            data.shifts_list.forEach(shift => {
                if (shift.cash_boxes && Array.isArray(shift.cash_boxes)) {
                    shift.cash_boxes.forEach(box => {
                        if (!cashBoxesTotal[box.name]) {
                            cashBoxesTotal[box.name] = 0;
                        }
                        cashBoxesTotal[box.name] += box.amount || 0;
                        cashBoxesGrandTotal += box.amount || 0;
                    });
                }
            });
        }

        // Display cash boxes in the "نقدي" metric
        const cashBoxesHtml = Object.keys(cashBoxesTotal).length > 0 
            ? Object.entries(cashBoxesTotal).map(([name, amount]) => `${name}: ${formatCurrency(amount)}`).join('<br>')
            : '0.00 ج.م';
        document.getElementById('metricCash').innerHTML = cashBoxesHtml;
        
        // Calculate total sum of all cash boxes
        document.getElementById('metricCashBoxesTotal').textContent = formatCurrency(cashBoxesGrandTotal);

        // Fetch and display profit summary
        fetchProfitSummary(start, end);

    // Shifts list and per-shift summary
    const shiftsList = document.getElementById('shiftsList');
    const shiftsSummary = document.getElementById('shiftsSummary');
    shiftsList.innerHTML = '';
    shiftsSummary.innerHTML = `<div class="text-muted">عدد الورديات في النطاق: ${data.shifts.count}</div>`;
    renderShifts(data);

        // Optionally show aggregated sale_items (top-selling)
        // Query backend if we want item-level aggregation; for now, keep placeholder
        const salesItemsTable = document.getElementById('salesItemsTable');
        salesItemsTable.innerHTML = '';
        
        // Render categories with collapsible items
        if (Array.isArray(data.categories_data) && data.categories_data.length > 0) {
            const categoriesContainer = document.createElement('div');
            categoriesContainer.className = 'categories-container';
            
            const header = document.createElement('h5');
            header.textContent = 'المبيعات حسب الفئة';
            header.style.marginBottom = '16px';
            categoriesContainer.appendChild(header);
            
            data.categories_data.forEach((category, index) => {
                const categoryCard = document.createElement('div');
                categoryCard.className = 'category-card';
                categoryCard.setAttribute('data-category-id', category.category_id || 'null');
                
                // Category header
                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'category-header';
                categoryHeader.innerHTML = `
                    <div class="category-info">
                        <div class="category-name">${category.category_name}</div>
                        <div class="category-stats">
                            <div class="category-stat">
                                <span class="category-stat-label">الكمية المباعة</span>
                                <span class="category-stat-value">${category.total_quantity.toFixed(0)}</span>
                            </div>
                            <div class="category-stat">
                                <span class="category-stat-label">إجمالي المبيعات</span>
                                <span class="category-stat-value">${formatCurrency(category.total_sales)}</span>
                            </div>
                            <div class="category-stat">
                                <span class="category-stat-label">عدد المنتجات</span>
                                <span class="category-stat-value">${category.items.length}</span>
                            </div>
                        </div>
                    </div>
                    <div class="category-toggle">
                        <i class="fas fa-chevron-down"></i>
                    </div>
                `;
                
                // Category items table
                const categoryItems = document.createElement('div');
                categoryItems.className = 'category-items';
                
                if (category.items && category.items.length > 0) {
                    const table = document.createElement('table');
                    table.className = 'category-items-table';
                    table.innerHTML = `
                        <thead>
                            <tr>
                                <th style="width: 60px; text-align: center;">الترتيب</th>
                                <th>اسم المنتج</th>
                                <th style="width: 120px; text-align: center;">الكمية</th>
                                <th style="width: 150px; text-align: center;">الإجمالي</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${category.items.map((item, itemIndex) => {
                                let rankClass = 'rank-other';
                                if (itemIndex === 0) rankClass = 'rank-1';
                                else if (itemIndex === 1) rankClass = 'rank-2';
                                else if (itemIndex === 2) rankClass = 'rank-3';
                                
                                return `
                                    <tr>
                                        <td style="text-align: center;">
                                            <span class="rank-badge ${rankClass}">${itemIndex + 1}</span>
                                        </td>
                                        <td><strong>${item.item_name}</strong></td>
                                        <td style="text-align: center;"><strong>${item.quantity.toFixed(0)}</strong></td>
                                        <td style="text-align: center;">${formatCurrency(item.total)}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    `;
                    categoryItems.appendChild(table);
                } else {
                    categoryItems.innerHTML = '<div class="empty-state"><p>لا توجد منتجات في هذه الفئة</p></div>';
                }
                
                // Toggle functionality
                categoryHeader.addEventListener('click', () => {
                    const isOpen = categoryItems.classList.contains('open');
                    
                    // Close all other categories
                    document.querySelectorAll('.category-items.open').forEach(item => {
                        if (item !== categoryItems) {
                            item.classList.remove('open');
                            item.previousElementSibling.classList.remove('active');
                        }
                    });
                    
                    // Toggle current category
                    if (isOpen) {
                        categoryItems.classList.remove('open');
                        categoryHeader.classList.remove('active');
                    } else {
                        categoryItems.classList.add('open');
                        categoryHeader.classList.add('active');
                    }
                });
                
                categoryCard.appendChild(categoryHeader);
                categoryCard.appendChild(categoryItems);
                categoriesContainer.appendChild(categoryCard);
            });
            
            salesItemsTable.appendChild(categoriesContainer);
        } else {
            salesItemsTable.innerHTML = '<div class="empty-state"><i class="fas fa-box-open"></i><p>لا توجد بيانات مبيعات لهذه الفترة</p></div>';
        }
        
        // Keep old top items for backward compatibility (hidden by default)
        if (Array.isArray(data.top_items) && data.top_items.length) {
            // You can remove this section if you don't need the old table anymore
        }

    } catch (err) {
        console.error(err);
        showError('فشل تحميل التقرير');
    }
    finally {
        showLoading(false);
    }
}

function applyPreset(days){
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (days - 1));
    document.getElementById('reportStart').value = start.toISOString().slice(0,10);
    document.getElementById('reportEnd').value = end.toISOString().slice(0,10);
    runReport();
}

function applyMonthPreset(){
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    document.getElementById('reportStart').value = start.toISOString().slice(0,10);
    document.getElementById('reportEnd').value = end.toISOString().slice(0,10);
    runReport();
}

function showLoading(show){
    let el = document.getElementById('reportsLoading');
    if (!el) {
        el = document.createElement('div');
        el.id = 'reportsLoading';
        el.className = 'reports-loading';
        el.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="sr-only">Loading...</span></div> تحميل...';
        const container = document.querySelector('.reports-container') || document.body;
        container.insertBefore(el, container.firstChild);
    }
    el.style.display = show ? 'block' : 'none';
}

function showError(msg){
    let el = document.getElementById('reportsError');
    if (!el) {
        el = document.createElement('div');
        el.id = 'reportsError';
        el.className = 'alert alert-danger';
        const container = document.querySelector('.reports-container') || document.body;
        container.insertBefore(el, container.firstChild);
    }
    el.textContent = msg;
}

function clearError(){
    const el = document.getElementById('reportsError');
    if (el) el.remove();
}

function showShiftDetails(e, shiftId) {
    e.stopPropagation();
    // reuse existing endpoints to populate a modal
    fetch(`/get_shift_summary_shifts/${shiftId}`)
        .then(r => r.json())
        .then(data => {
            // open a simple modal with summary
            const cashBoxesHtml = data.cash_boxes && data.cash_boxes.length > 0 
                ? '<h5>الصناديق:</h5>' + data.cash_boxes.map(cb => `<p>${cb.name}: ${formatCurrency(cb.amount)}</p>`).join('')
                : '';
            const content = `
                <div class="card p-3">
                    <h4>تفاصيل الوردية ${shiftId}</h4>
                    <p>إجمالي المبيعات: ${formatCurrency(data.total_sales || 0)}</p>
                    <p>المصروفات: ${formatCurrency(data.total_expenses || 0)}</p>
                    <p>المرتجعات: ${formatCurrency(data.total_returns || 0)}</p>
                    <p>عدد الطلبات: ${data.orders_count || 0}</p>
                    <p>الربح: ${formatCurrency(data.profit || 0)}</p>
                    <p>نقدي: ${formatCurrency(data.cash_amount || 0)}</p>
                    
                    ${cashBoxesHtml}
                </div>
            `;
            showInlineModal(content);
        })
        .catch(err => { console.error(err); alert('فشل جلب تفاصيل الوردية'); });
}

function showInlineModal(html) {
    // remove existing modal
    const existing = document.querySelector('.reports-inline-modal');
    if (existing) existing.remove();
    const wrapper = document.createElement('div');
    wrapper.className = 'reports-inline-modal detail-modal-backdrop';
    wrapper.innerHTML = `<div class="detail-modal">${html}<div style="text-align:left;margin-top:10px"><button class="btn btn-sm btn-secondary" onclick="document.querySelector('.reports-inline-modal').remove()">إغلاق</button></div></div>`;
    document.body.appendChild(wrapper);
}

window.addEventListener('resize', () => {
    if (lastData) renderShifts(lastData);
});

async function fetchProfitSummary(startDate, endDate) {
    try {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);

        const res = await fetch('/api/profit_summary?' + params.toString());
        const data = await res.json();
        
        if (!data.success) {
            console.error('Error fetching profit summary:', data.error);
            // Set default values on error
            document.getElementById('totalSalesValue').textContent = '0.00 ج.م';
            document.getElementById('totalCostValue').textContent = '0.00 ج.م';
            document.getElementById('totalExpensesValue').textContent = '0.00 ج.م';
            document.getElementById('netProfitValue').textContent = '0.00 ج.م';
            return;
        }

        // Update profit summary table
        document.getElementById('totalSalesValue').textContent = formatCurrency(data.total_sales);
        document.getElementById('totalCostValue').textContent = formatCurrency(data.cost_of_sales);
        document.getElementById('totalExpensesValue').textContent = formatCurrency(data.total_expenses);
        document.getElementById('netProfitValue').textContent = formatCurrency(data.net_profit);
        
        // Apply color coding for net profit
        const netProfitCell = document.getElementById('netProfitValue');
        if (data.net_profit < 0) {
            netProfitCell.style.color = '#dc3545'; // Red for loss
        } else if (data.net_profit > 0) {
            netProfitCell.style.color = '#28a745'; // Green for profit
        } else {
            netProfitCell.style.color = '#6c757d'; // Gray for zero
        }
    } catch (err) {
        console.error('Failed to fetch profit summary:', err);
        // Set default values on error
        document.getElementById('totalSalesValue').textContent = '0.00 ج.م';
        document.getElementById('totalCostValue').textContent = '0.00 ج.م';
        document.getElementById('totalExpensesValue').textContent = '0.00 ج.م';
        document.getElementById('netProfitValue').textContent = '0.00 ج.م';
    }
}
