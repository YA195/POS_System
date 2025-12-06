document.addEventListener('DOMContentLoaded', function() {
    loadShifts();
    loadDeliveryWorkers();

    // Add event listeners
    const shiftSelect = document.getElementById('shiftSelect');
    const deliveryWorkerSelect = document.getElementById('deliveryWorkerFeesSelect');
    const loadBtn = document.getElementById('loadCompletedOrdersBtn');
    const payBtn = document.getElementById('payDeliveryFeesBtn');

    if (shiftSelect) {
        shiftSelect.addEventListener('change', loadCompletedOrders);
    }

    if (deliveryWorkerSelect) {
        deliveryWorkerSelect.addEventListener('change', loadCompletedOrders);
    }

    if (loadBtn) {
        loadBtn.addEventListener('click', loadCompletedOrders);
    }

    if (payBtn) {
        payBtn.addEventListener('click', () => {
            const workerId = deliveryWorkerSelect.value;
            const shiftId = shiftSelect.value;
            payDeliveryFees(workerId, shiftId);
        });
    }
});

function loadShifts() {
    console.log('Loading shifts...');
    fetch('/get_shifts')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('shiftSelect');
                select.innerHTML = '<option value="">اختر الوردية</option>';

                data.shifts.forEach(shift => {
                    const option = document.createElement('option');
                    option.value = shift.id;
                    option.textContent = `${shift.name} (${shift.date})`;
                    // Default to current shift if it's today
                    if (shift.is_current) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });

                // Load completed orders if a shift is selected
                if (select.value) {
                    loadCompletedOrders();
                }
            } else {
                console.error('Error loading shifts:', data.error);
                showAlert('error', 'حدث خطأ أثناء تحميل الورديات');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'حدث خطأ أثناء تحميل الورديات');
        });
}

function loadDeliveryWorkers() {
    console.log('Loading delivery workers...');
    fetch('/get_delivery_workers_dlev')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('deliveryWorkerFeesSelect');
                select.innerHTML = '<option value="">اختر عامل التوصيل</option>';

                data.workers.forEach(worker => {
                    const option = document.createElement('option');
                    option.value = worker.id;
                    option.textContent = worker.name;
                    select.appendChild(option);
                });
            } else {
                console.error('Error loading delivery workers:', data.error);
                showAlert('error', 'حدث خطأ أثناء تحميل عمال التوصيل');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'حدث خطأ أثناء تحميل عمال التوصيل');
        });
}

function loadCompletedOrders() {
    const shiftId = document.getElementById('shiftSelect').value;
    const deliveryWorkerId = document.getElementById('deliveryWorkerFeesSelect').value;
    const payButton = document.getElementById('payDeliveryFeesBtn');

    if (!shiftId || !deliveryWorkerId) {
        document.querySelector('.fees-summary').style.display = 'none';
        document.querySelector('.completed-orders-table').style.display = 'none';
        document.getElementById('noCompletedOrdersMessage').style.display = 'none';
        return;
    }

    fetch(`/get_completed_orders_by_shift/${shiftId}/${deliveryWorkerId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.orders.length > 0) {
                    displayCompletedOrders(data.orders);
                    updateFeesStats(data.orders);
                    document.querySelector('.fees-summary').style.display = 'block';
                    document.querySelector('.completed-orders-table').style.display = 'block';
                    document.getElementById('noCompletedOrdersMessage').style.display = 'none';

                    // Show pay button only if there are completed orders with fees
                    const totalFees = data.orders.reduce((sum, order) => sum + order.delivery_fee, 0);
                    payButton.style.display = totalFees > 0 ? 'block' : 'none';
                } else {
                    document.querySelector('.fees-summary').style.display = 'none';
                    document.querySelector('.completed-orders-table').style.display = 'none';
                    document.getElementById('noCompletedOrdersMessage').style.display = 'block';
                    payButton.style.display = 'none';
                }
            } else {
                showAlert('error', data.error || 'حدث خطأ أثناء تحميل الطلبات المكتملة');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'حدث خطأ أثناء تحميل الطلبات المكتملة');
        });
}

function displayCompletedOrders(orders) {
    const tbody = document.getElementById('completedOrdersList');
    tbody.innerHTML = '';

    orders.forEach(order => {
        // Main row
        const row = document.createElement('tr');
        row.className = 'order-main-row';
        // Prepare a short address to keep the row compact
        const shortAddress = order.address && order.address.length > 50 ? order.address.slice(0, 50) + '...' : (order.address || '-');

        row.innerHTML = `
            <td><span class="toggle-details"><i class="fas fa-chevron-down"></i></span> ${order.sale_number}</td>
            <td><strong>${order.customer_name}</strong></td>
            <td>${order.customer_phone || '-'}</td>
            <td>${shortAddress}</td>
            <td>${order.final_amount.toFixed(2)} ج.م</td>
            <td>${order.delivery_fee.toFixed(2)} ج.م</td>
            <td>${order.completed_at}</td>
        `;

        // Details row (hidden by default)
        const detailsRow = document.createElement('tr');
        detailsRow.className = 'order-details-row';
        detailsRow.id = `details-${order.id}`;
        detailsRow.style.display = 'none';
    // detailsRow colspan must match number of visible columns (7)
    detailsRow.innerHTML = `<td colspan="7"><div class="order-details-content">جاري التحميل...</div></td>`;

        // Toggle behaviour: expand inline under the row
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => {
            const icon = row.querySelector('.toggle-details i');

            // Close other open details rows (optional: keep only one open)
            document.querySelectorAll('.order-details-row').forEach(r => {
                if (r.id !== detailsRow.id) {
                    r.style.display = 'none';
                    const otherIcon = r.previousSibling && r.previousSibling.querySelector ? r.previousSibling.querySelector('.toggle-details i') : null;
                    if (otherIcon) otherIcon.className = 'fas fa-chevron-down';
                }
            });

            if (detailsRow.style.display === 'none') {
                // Load details if not already loaded
                const contentDiv = detailsRow.querySelector('.order-details-content');
                if (!contentDiv.dataset.loaded) {
                    loadOrderDetailsInline(order.id, contentDiv);
                }
                detailsRow.style.display = 'table-row';
                if (icon) icon.className = 'fas fa-chevron-up';
            } else {
                detailsRow.style.display = 'none';
                if (icon) icon.className = 'fas fa-chevron-down';
            }
        });

        tbody.appendChild(row);
        tbody.appendChild(detailsRow);
    });
}

// Load details and render inline into the provided content div
function loadOrderDetailsInline(orderId, contentDiv) {
    fetch(`/get_order_details_dlev/${orderId}`)
        .then(resp => resp.json())
        .then(data => {
            if (data.success) {
                // Use compact inline renderer (omit customer/phone/address which are in columns)
                contentDiv.innerHTML = buildOrderDetailsInlineHtml(data.order, data.items);
                contentDiv.dataset.loaded = 'true';
            } else {
                contentDiv.innerHTML = `<div class="text-danger">${data.error || 'خطأ في جلب التفاصيل'}</div>`;
            }
        })
        .catch(err => {
            console.error('Error fetching order details:', err);
            contentDiv.innerHTML = `<div class="text-danger">خطأ في جلب التفاصيل</div>`;
        });
}

// Build HTML for order details (shared by modal and inline)
function buildOrderDetailsHtml(order, items) {
    return `
        <div class="order-summary">
            <p><strong>رقم الفاتورة:</strong> ${order.sale_number}</p>
            <p><strong>العميل:</strong> ${order.customer_name} | <strong>الهاتف:</strong> ${order.customer_phone}</p>
            <p><strong>العنوان:</strong> ${order.address}</p>
            <p><strong>طريقة الدفع:</strong> ${order.payment_method}</p>
            <p><strong>الوقت:</strong> ${order.created_at}</p>
            <p><strong>المبلغ الإجمالي:</strong> ${order.total_amount.toFixed(2)} ج.م</p>
            <p><strong>المبلغ النهائي:</strong> ${order.final_amount.toFixed(2)} ج.م</p>
            <p><strong>رسوم التوصيل:</strong> ${order.delivery_fee.toFixed(2)} ج.م</p>
        </div>
        <div class="order-items mt-2">
            <h6>العناصر</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead><tr><th>الصنف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
                    <tbody>
                        ${items.map(i => `
                            <tr>
                                <td>${i.name}</td>
                                <td>${i.quantity}</td>
                                <td>${i.unit_price.toFixed(2)}</td>
                                <td>${i.total_price.toFixed(2)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

// Compact inline details HTML: excludes customer/phone/address because these are shown in table columns
function buildOrderDetailsInlineHtml(order, items) {
    return `
        <div class="order-summary">
            <p><strong>رقم الفاتورة:</strong> ${order.sale_number}</p>
            <p><strong>الوقت:</strong> ${order.created_at}</p>
            <p><strong>طريقة الدفع:</strong> ${order.payment_method}</p>
            <p><strong>المبلغ النهائي:</strong> ${order.final_amount.toFixed(2)} ج.م</p>
            <p><strong>رسوم التوصيل:</strong> ${order.delivery_fee.toFixed(2)} ج.م</p>
        </div>
        <div class="order-items mt-2">
            <h6>العناصر</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead><tr><th>الصنف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
                    <tbody>
                        ${items.map(i => `
                            <tr>
                                <td>${i.name}</td>
                                <td>${i.quantity}</td>
                                <td>${i.unit_price.toFixed(2)}</td>
                                <td>${i.total_price.toFixed(2)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function loadOrderDetailsForModal(orderId) {
    fetch(`/get_order_details_dlev/${orderId}`)
        .then(resp => resp.json())
        .then(data => {
            if (data.success) {
                renderOrderDetailsModal(data.order, data.items);
                $('#orderDetailsModal').modal('show');
            } else {
                showAlert('error', data.error || 'خطأ في جلب تفاصيل الطلب');
            }
        })
        .catch(err => {
            console.error('Error fetching order details:', err);
            showAlert('error', 'خطأ في جلب تفاصيل الطلب');
        });
}

function renderOrderDetailsModal(order, items) {
    const container = document.getElementById('orderDetailsContent');
    container.innerHTML = `
        <div class="order-summary">
            <p><strong>رقم الفاتورة:</strong> ${order.sale_number}</p>
            <p><strong>العميل:</strong> ${order.customer_name} | <strong>الهاتف:</strong> ${order.customer_phone}</p>
            <p><strong>العنوان:</strong> ${order.address}</p>
            <p><strong>طريقة الدفع:</strong> ${order.payment_method}</p>
            <p><strong>الوقت:</strong> ${order.created_at}</p>
            <p><strong>المبلغ الإجمالي:</strong> ${order.total_amount.toFixed(2)} ج.م</p>
            <p><strong>المبلغ النهائي:</strong> ${order.final_amount.toFixed(2)} ج.م</p>
            <p><strong>رسوم التوصيل:</strong> ${order.delivery_fee.toFixed(2)} ج.م</p>
        </div>
        <hr />
        <div class="order-items">
            <h6>العناصر</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead><tr><th>الصنف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
                    <tbody>
                        ${items.map(i => `
                            <tr>
                                <td>${i.name}</td>
                                <td>${i.quantity}</td>
                                <td>${i.unit_price.toFixed(2)}</td>
                                <td>${i.total_price.toFixed(2)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function updateFeesStats(orders) {
    const totalFees = orders.reduce((sum, order) => sum + order.delivery_fee, 0);
    document.getElementById('completedOrdersCount').textContent = orders.length;
    document.getElementById('totalDeliveryFees').textContent = totalFees.toFixed(2) + ' ج.م';
}

function payDeliveryFees(deliveryWorkerId, shiftId) {
    const totalFees = parseFloat(document.getElementById('totalDeliveryFees').textContent.replace(' ج.م', ''));

    if (!confirm(`هل أنت متأكد من دفع مبلغ ${totalFees.toFixed(2)} ج.م؟`)) {
        return;
    }

    fetch('/pay_delivery_fees_by_shift', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            delivery_worker_id: deliveryWorkerId,
            shift_id: shiftId,
            amount: totalFees
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('success', 'تم دفع رسوم التوصيل بنجاح');
            loadCompletedOrders(); // Refresh the orders
        } else {
            showAlert('error', data.error || 'حدث خطأ أثناء دفع رسوم التوصيل');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'حدث خطأ أثناء دفع رسوم التوصيل');
    });
}

function showAlert(type, message) {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="close" data-dismiss="alert">
            <span>&times;</span>
        </button>
    `;

    // Find or create alert container
    let alertContainer = document.querySelector('.alert-container');
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.className = 'alert-container';
        document.querySelector('.delivery-content').prepend(alertContainer);
    }

    // Add alert to container
    alertContainer.appendChild(alertDiv);

    // Auto dismiss after 3 seconds
    setTimeout(() => alertDiv.remove(), 3000);
}
