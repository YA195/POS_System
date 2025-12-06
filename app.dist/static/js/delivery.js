document.addEventListener('DOMContentLoaded', function() {
    // Debug logs
    console.log('Delivery page script loaded');
    
    // Initialize buttons and event listeners
    const loadDeliveryBtn = document.getElementById('loadDeliveryOrders');
    console.log('Load button found:', !!loadDeliveryBtn);

    // Load data immediately when page loads
    loadDeliveryWorkers();
    loadPendingOrders();

    // Add button event listeners
    if (loadDeliveryBtn) {
        loadDeliveryBtn.addEventListener('click', loadPendingOrders);
    }

    // Initialize select all checkbox
    const selectAllCheckbox = document.getElementById('selectAllOrders');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            document.querySelectorAll('.order-checkbox').forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateStats();
        });
    }

    // Add event listener for the mark as done button
    const markAsPaidBtn = document.getElementById('markAsPaidBtn');
    if (markAsPaidBtn) {
        markAsPaidBtn.addEventListener('click', markSelectedOrdersAsDone);
    }
});

function loadDeliveryWorkers() {
    console.log('Loading delivery workers...');
    fetch('/get_delivery_workers_dlev')
        .then(response => response.json())
        .then(data => {
            console.log('Delivery workers data:', data);
            if (data.success) {
                const select = document.getElementById('deliveryWorkerSelect');
                select.innerHTML = '<option value="">اختر عامل التوصيل</option>';
                
                data.workers.forEach(worker => {
                    const option = document.createElement('option');
                    option.value = worker.id;
                    option.textContent = worker.name;
                    select.appendChild(option);
                });
            } else {
                console.error('Error loading delivery workers:', data.error);
            }
        })
        .catch(error => console.error('Error:', error));
}

function loadPendingOrders() {
    console.log('Loading pending orders...');
    const tbody = document.getElementById('deliveryOrdersList');
    const deliveryWorkerId = document.getElementById('deliveryWorkerSelect').value;
    
    if (!tbody) return;

    setLoadingState(true);
    tbody.innerHTML = '<tr><td colspan="10" class="text-center">جاري التحميل...</td></tr>';

    fetch('/get_pending_orders')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Filter orders based on delivery worker
                let filteredOrders = data.orders;
                if (deliveryWorkerId) {
                    // Show only orders assigned to this delivery worker
                    filteredOrders = data.orders.filter(order => 
                        order.delivery_worker_id === parseInt(deliveryWorkerId)
                    );
                }
                
                displayOrders(filteredOrders);
                updateStats(filteredOrders); // This will update with filtered orders
            } else {
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'حدث خطأ أثناء تحميل الطلبات');
        })
        .finally(() => setLoadingState(false));
}

// Update the button text to reflect the filter state
function setLoadingState(isLoading) {
    const loadDeliveryBtn = document.getElementById('loadDeliveryOrders');
    if (!loadDeliveryBtn) return;
    
    const deliveryWorkerSelect = document.getElementById('deliveryWorkerSelect');
    const selectedWorkerName = deliveryWorkerSelect.options[deliveryWorkerSelect.selectedIndex].text;
    
    loadDeliveryBtn.disabled = isLoading;
    if (isLoading) {
        loadDeliveryBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التحميل...';
    } else {
        if (deliveryWorkerSelect.value) {
            loadDeliveryBtn.innerHTML = `<i class="fas fa-sync-alt"></i> عرض طلبات ${selectedWorkerName}`;
        } else {
            loadDeliveryBtn.innerHTML = '<i class="fas fa-sync-alt"></i> تحديث الطلبات';
        }
    }
}

function displayOrders(orders) {
    const tbody = document.getElementById('deliveryOrdersList');
    const noOrdersMessage = document.getElementById('noOrdersMessage');
    
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!orders || orders.length === 0) {
        noOrdersMessage.style.display = 'block';
        return;
    }

    noOrdersMessage.style.display = 'none';
    orders.forEach(order => {
        const [row, detailsRow] = createOrderRow(order);
        tbody.appendChild(row);
        tbody.appendChild(detailsRow);
    });
}

// Update createOrderRow function to add click handler
function createOrderRow(order) {
    // Create main row
    const row = document.createElement('tr');
    row.classList.add('order-row');
    row.dataset.orderId = order.id;
    row.innerHTML = `
        <td class="clickable">${order.sale_number}</td>
        <td class="clickable">${order.delivery_worker_name}</td>
        <td class="clickable">${order.customer_name || '-'}</td>
        <td class="clickable">${order.customer_phone || '-'}</td>
        <td class="clickable">${order.final_amount.toFixed(2)} ج.م</td>
        <td class="clickable">${order.delivery_fee.toFixed(2)} ج.م</td>
        <td class="clickable">${order.payment_method || 'نقدي'}</td>
        <td class="clickable">${order.created_at}</td>
        <td class="no-click">
            <button class="expand-btn" onclick="toggleOrderDetails(${order.id}, this)">
                <i class="fas fa-chevron-down"></i>
            </button>
        </td>
    `;

    // Add click handler for row
    row.addEventListener('click', function(e) {
        // Only proceed if clicking a clickable cell
        if (!e.target.classList.contains('clickable')) {
            return;
        }
        
        const deliveryWorkerId = document.getElementById('deliveryWorkerSelect').value;
        if (!deliveryWorkerId) {
            showAlert('warning', 'الرجاء اختيار عامل توصيل أولاً');
            return;
        }

        assignDeliveryWorker(order.id, deliveryWorkerId, row);
    });

    // Create details row (unchanged)
    const detailsRow = document.createElement('tr');
    detailsRow.className = 'order-details-row';
    detailsRow.id = `details-${order.id}`;
    detailsRow.style.display = 'none';
    detailsRow.innerHTML = `
        <td colspan="10">
            <div class="order-details-content p-3">
                <div class="loading-spinner text-center">
                    <i class="fas fa-spinner fa-spin"></i> جاري التحميل...
                </div>
            </div>
        </td>
    `;

    // Return both rows as array
    return [row, detailsRow];
}

// Add new function to handle assignment
function assignDeliveryWorker(orderId, deliveryWorkerId, row) {
    console.log('Assigning delivery worker:', {
        orderId: orderId,
        deliveryWorkerId: deliveryWorkerId
    });

    fetch('/assign_delivery_worker', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            delivery_worker_id: deliveryWorkerId,
            order_ids: [orderId] // Make sure orderId is sent as an array
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Assignment response:', data);
        if (data.success) {
            // Update row visually
            const workerName = document.getElementById('deliveryWorkerSelect')
                .options[document.getElementById('deliveryWorkerSelect').selectedIndex].text;
            
            // Update row visually
            row.querySelector('td:nth-child(2)').textContent = workerName;
            
            // Show success message
            showAlert('success', 'تم تعيين عامل التوصيل بنجاح');
            
            // Highlight the row briefly
            row.classList.add('assignment-success');
            setTimeout(() => row.classList.remove('assignment-success'), 2000);
        } else {
            showAlert('error', data.error || 'حدث خطأ أثناء تعيين عامل التوصيل');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'حدث خطأ أثناء تعيين عامل التوصيل');
    });
}

function markSelectedOrdersAsDone() {
    const deliveryWorkerId = document.getElementById('deliveryWorkerSelect').value;
    
    if (!deliveryWorkerId) {
        showAlert('warning', 'الرجاء اختيار عامل توصيل أولاً');
        return;
    }

    // Get all orders for the selected delivery worker
    fetch('/get_pending_orders')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Filter orders for selected delivery worker
                const ordersToMark = data.orders.filter(order => 
                    order.delivery_worker_id === parseInt(deliveryWorkerId) &&
                    order.status === 'assigned'
                );

                if (ordersToMark.length === 0) {
                    showAlert('warning', 'لا توجد طلبات معينة لهذا المندوب');
                    return;
                }

                // Confirm before proceeding
                if (!confirm(`هل أنت متأكد من تحصيل المبالغ لعدد ${ordersToMark.length} طلبات؟`)) {
                    return;
                }

                // Mark orders as done
                fetch('/mark_orders_as_done', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        order_ids: ordersToMark.map(order => order.id)
                    })
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        showAlert('success', 'تم تحصيل المبالغ بنجاح');
                        // Remove marked orders and update display
                        ordersToMark.forEach(order => {
                            const row = document.querySelector(`tr[data-order-id="${order.id}"]`);
                            const detailsRow = document.getElementById(`details-${order.id}`);
                            if (row) row.remove();
                            if (detailsRow) detailsRow.remove();
                        });
                        // Reload orders and update stats
                        loadPendingOrders();
                    } else {
                        showAlert('error', result.error || 'حدث خطأ أثناء تحصيل المبالغ');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showAlert('error', 'حدث خطأ أثناء تحصيل المبالغ');
                });
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'حدث خطأ أثناء تحميل الطلبات');
        });
}

function displayCompletedOrders(orders) {
    const tbody = document.getElementById('completedOrdersList');
    tbody.innerHTML = '';

    orders.forEach(order => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${order.sale_number}</td>
            <td>${order.customer_name}</td>
            <td>${order.final_amount.toFixed(2)} ج.م</td>
            <td>${order.delivery_fee.toFixed(2)} ج.م</td>
            <td>${order.created_at}</td>
        `;
        tbody.appendChild(row);
    });
}

function updateStats(orders) {
    const totalAmount = orders.reduce((sum, order) => sum + order.final_amount, 0);
    const totalDeliveryFees = orders.reduce((sum, order) => sum + (order.delivery_fee || 0), 0);
    
    document.getElementById('ordersCount').textContent = orders.length;
    document.getElementById('totalAmount').textContent = totalAmount.toFixed(2) + ' ج.م';
    
    // Update delivery fees total if you have this element
    const deliveryFeesElement = document.getElementById('totalDeliveryFees');
    if (deliveryFeesElement) {
        deliveryFeesElement.textContent = totalDeliveryFees.toFixed(2) + ' ج.م';
    }
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

function toggleOrderDetails(orderId, button) {
    const detailsRow = document.getElementById(`details-${orderId}`);
    const icon = button.querySelector('i');
    
    if (detailsRow.style.display === 'none') {
        detailsRow.style.display = 'table-row';
        icon.className = 'fas fa-chevron-up';
        loadOrderDetails(orderId);
    } else {
        detailsRow.style.display = 'none';
        icon.className = 'fas fa-chevron-down';
    }
}

function loadOrderDetails(orderId) {
    fetch(`/get_order_details_dlev/${orderId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const detailsRow = document.getElementById(`details-${orderId}`);
                detailsRow.querySelector('.order-details-content').innerHTML = `
                    <div class="compact-details">
                        <div class="customer-info">
                            <small><strong>العميل:</strong> ${data.order.customer_name || '-'}</small>
                            <small><strong>الهاتف:</strong> ${data.order.customer_phone || '-'}</small>
                            <small><strong>العنوان:</strong> ${data.order.address}</small>
                        </div>
                        <div class="items-table mt-2">
                            <table class="table table-sm">
                                <tbody>
                                    ${data.items.map(item => `
                                        <tr>
                                            <td>${item.name}</td>
                                            <td>${item.quantity}</td>
                                            <td>${item.total_price.toFixed(2)} </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
        })
        .catch(error => console.error('Error:', error));
}

// Make functions available globally
window.showOrderDetails = showOrderDetails;
window.toggleOrderDetails = toggleOrderDetails;