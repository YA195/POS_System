// Global Variables
const PHONE_LENGTH = 11;
// When a phone number is completed we set a short block window to avoid
// accidental Save (F10 / saveSale) being triggered by the last key event
// or by any synthetic event that immediately follows typing the 11th digit.
const PHONE_COMPLETE_BLOCK_MS = 800; // milliseconds
let lastPhoneCompletedAt = 0;
// Inline message helper - shows a temporary message next to an input element
function showInlineMessage(el, msg, timeout = 3000) {
    if (!el) return;
    // ensure a container exists
    let msgEl = el.parentElement.querySelector('.inline-message');
    if (!msgEl) {
        msgEl = document.createElement('div');
        msgEl.className = 'inline-message';
        msgEl.style.color = 'red';
        msgEl.style.fontSize = '0.9em';
        msgEl.style.marginTop = '4px';
        el.parentElement.appendChild(msgEl);
    }
    msgEl.textContent = msg;
    if (msgEl._hideTimer) clearTimeout(msgEl._hideTimer);
    msgEl._hideTimer = setTimeout(() => { msgEl.textContent = ''; }, timeout);
}
let debounceTimer;
let currentTableIndex = 1;
let lastSaleId = null;
const totalTables = 5;
let salesTables = Array(totalTables).fill().map(() => ({
    items: [],
    delivery: {
        phone: '',
        name: '',
        address1: '',
        address2: '',
        address3: '',
        service: ''
    },
    discount: 0,
    payment: 'cash',
    print: false
}));
let manualBarcodeMode = false;
// Cache last saved customer by phone to detect edits
const lastSavedCustomerByPhone = {};

// Phone Number Handling
function handlePhoneNumberInput(value) {
    value = value.replace(/[^0-9]/g, '').slice(0, PHONE_LENGTH);
    
    if (value.length >= 3 && value.length < PHONE_LENGTH) {
        fetchPhoneSuggestions(value);
    } else {
        hidePhoneSuggestions();
    }

    if (value.length === PHONE_LENGTH) {
        handleCompletePhoneNumber(value);
    }
    
    return value;
}

// Select-all helper for inputs
function selectAllOnFocus(el) {
    el.addEventListener('focus', function() { this.select && this.select(); });
    el.addEventListener('click', function() { this.select && this.select(); });
}

// Clear customer-related input fields
function clearCustomerFields() {
    const name = document.getElementById('customerName');
    const addr1 = document.getElementById('addressLine1');
    const addr2 = document.getElementById('addressLine2');
    const addr3 = document.getElementById('addressLine3');
    if (name) name.value = '';
    if (addr1) addr1.value = '';
    if (addr2) addr2.value = '';
    if (addr3) addr3.value = '';
    const history = document.querySelector('.customer-history-section');
    if (history) history.style.display = 'none';
}

function handleCompletePhoneNumber(phone) {
    // mark completion time to prevent accidental save immediately after typing
    try { lastPhoneCompletedAt = Date.now(); } catch (err) {}
    loadCustomerData(phone);
    const deliveryService = document.getElementById('deliveryService');
    if (deliveryService) {
        deliveryService.required = true;
        // Do not show a blocking alert here. Instead, focus the delivery fee
        // control so the cashier can enter it. Alerts are disruptive and were
        // firing unexpectedly when phone input finished.
        if (!deliveryService.value) {
            deliveryService.focus();
        }
    }
}

function fetchPhoneSuggestions(value) {
    fetch(`/get_phone_suggestions/${value}`)
        .then(response => response.json())
        .then(data => showPhoneSuggestions(data.suggestions))
        .catch(error => console.error('Error:', error));
}

// Customer Data Loading


function fillCustomerData(customer) {
    document.getElementById('customerName').value = customer.name || '';
    document.getElementById('addressLine1').value = customer.address_line1 || '';
    document.getElementById('addressLine2').value = customer.address_line2 || '';
    document.getElementById('addressLine3').value = customer.address_line3 || '';
    // cache loaded customer to avoid redundant saves
    if (customer.phone) lastSavedCustomerByPhone[customer.phone] = {
        name: customer.name || '',
        address_line1: customer.address_line1 || '',
        address_line2: customer.address_line2 || '',
        address_line3: customer.address_line3 || ''
    };
}

// Debounced auto-save customer when phone,name and at least one address field are provided
let autoSaveTimer = null;
function scheduleAutoSaveCustomer() {
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(autoSaveCustomer, 800);
}

function autoSaveCustomer() {
    const phone = document.getElementById('phoneNumber').value.trim();
    const name = document.getElementById('customerName').value.trim();
    const addr1 = document.getElementById('addressLine1').value.trim();
    const addr2 = document.getElementById('addressLine2').value.trim();
    const addr3 = document.getElementById('addressLine3').value.trim();

    if (!phone || phone.length !== PHONE_LENGTH) return;
    if (!name && !addr1 && !addr2 && !addr3) return; // nothing to save

    // compare with last saved to avoid duplicate requests
    const last = lastSavedCustomerByPhone[phone] || {};
    if (last.name === name && last.address_line1 === addr1 && last.address_line2 === addr2 && last.address_line3 === addr3) {
        return;
    }

    const payload = {
        phone: phone,
        name: name,
        address_line1: addr1,
        address_line2: addr2,
        address_line3: addr3
    };

    fetch('/save_customer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            lastSavedCustomerByPhone[phone] = { name, address_line1: addr1, address_line2: addr2, address_line3: addr3 };
            // show small toast or console log
            console.log('Customer saved/updated for', phone);
        } else {
            console.warn('Failed to save customer:', data.error);
        }
    })
    .catch(err => console.error('Error saving customer:', err));
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    checkActiveShift();
});

function initializeEventListeners() {
    // Phone number input
    const phoneInput = document.getElementById('phoneNumber');
    // Centralized phone input behavior: while typing keep customer fields clear
    phoneInput.addEventListener('input', function(e) {
        this.value = handlePhoneNumberInput(this.value);
        const v = this.value.replace(/[^0-9]/g, '');
        if (v.length < PHONE_LENGTH) {
            // keep fields empty while user types
            clearCustomerFields();
        } else if (v.length === PHONE_LENGTH) {
            hidePhoneSuggestions();
            loadCustomerData(v);
        }
    });

    // make phone input select all on focus/click
    selectAllOnFocus(phoneInput);

    // auto-save listeners for customer fields
    const customerNameInput = document.getElementById('customerName');
    const addr1 = document.getElementById('addressLine1');
    const addr2 = document.getElementById('addressLine2');
    const addr3 = document.getElementById('addressLine3');

    [customerNameInput, addr1, addr2, addr3].forEach(el => {
        el.addEventListener('input', scheduleAutoSaveCustomer);
        // select all on focus for convenience
        el.addEventListener('focus', function(){ this.select && this.select(); });
    });

    // Delivery service
    document.getElementById('deliveryService').addEventListener('change', function() {
        validateDeliveryFee(this);
        updateTotals();
    });

    // Sales related listeners
    document.getElementById('discountAmount').addEventListener('input', validateDiscount);
    document.getElementById('paidAmount').addEventListener('input', updateTotals);
    
    // Initialize other event listeners...
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {

    // Load cash boxes for payment method dropdown
    loadCashBoxes();

    // Check for active shift first
    fetch('/check_active_shift')
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('خطأ في التحقق من الوردية');
                return;
            }

            // Continue with page initialization
            loadQuickItems();
            setupKeyboardShortcuts();

            document.getElementById('prevTable').addEventListener('click', () => {
                switchTable(currentTableIndex - 1);
                document.getElementById('barcodeInput').focus();
            });

            document.getElementById('nextTable').addEventListener('click', () => {
                switchTable(currentTableIndex + 1);
                document.getElementById('barcodeInput').focus();
            });

            // Initialize first table
            document.getElementById('prevTable').disabled = true;
            document.getElementById('currentTable').textContent = '1';
            document.getElementById('totalTables').textContent = totalTables;
        })
        .catch(error => {
            console.error('Error:', error);
            alert('خطأ في التحقق من الوردية');
        });

    // Add manual barcode checkbox
    const controlPanel = document.querySelector('.form-group');
    const checkboxDiv = document.createElement('div');
    checkboxDiv.className = 'manual-barcode-control';

    controlPanel.appendChild(checkboxDiv);

    // Add checkbox event listener
    document.getElementById('manualBarcodeCheck').addEventListener('change', function() {
        manualBarcodeMode = this.checked;
        const barcodeInput = document.getElementById('barcodeInput');
        barcodeInput.focus();
    });
});

document.getElementById('barcodeInput').addEventListener('input', function(e) {
    if (!manualBarcodeMode) {
        clearTimeout(debounceTimer);
        const barcode = e.target.value;

        if (barcode) {
            debounceTimer = setTimeout(() => {
                addItemToSales(barcode);
                this.value = ''; // Clear input after delay
            }, 500);
        }
    }
});

document.getElementById('barcodeInput').addEventListener('keydown', function(e) {
    if (manualBarcodeMode && e.key === 'Enter') {
        e.preventDefault();
        const barcode = this.value;
        if (barcode) {
            addItemToSales(barcode);
            this.value = ''; // Clear input after adding item
            manualBarcodeMode = false;
            document.getElementById('manualBarcodeCheck').checked = false;
        }
    }
});

document.getElementById('productName').addEventListener('input', function(e) {
    const searchTerm = this.value.trim();
    if (searchTerm.length >= 2) {
        fetch(`/search_items/${encodeURIComponent(searchTerm)}`)
            .then(response => response.json())
            .then(data => {
                if (Array.isArray(data)) {
                    showSearchResults(data);
                } else {
                    console.error('Expected array, got:', data);
                }
            })
            .catch(error => console.error('Error:', error));
    } else {
        hideSearchResults();
    }
});

// Add to your existing script section
document.getElementById('discountAmount').addEventListener('focus', function() {
    this.select();
});

// Functions
// Add this function to your existing script block

function loadCashBoxes() {
    fetch('/get_cash_boxes')
        .then(response => response.json())
        .then(boxes => {
            const paymentSelect = document.getElementById('paymentMethod');
            paymentSelect.innerHTML = '';
            
            if (boxes.length === 0) {
                paymentSelect.innerHTML = '<option value="">لا توجد صناديق</option>';
                return;
            }
            
            // Find "نقدي" cash box or default to first box
            let defaultBoxFound = false;
            
            // Add each cash box as an option
            boxes.forEach((box, index) => {
                const option = document.createElement('option');
                option.value = box.id;
                option.textContent = box.name;
                // Select "نقدي" box by default, or first box if "نقدي" not found
                if (box.name === 'نقدي' || (!defaultBoxFound && index === 0)) {
                    option.selected = true;
                    defaultBoxFound = true;
                }
                paymentSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading cash boxes:', error);
            const paymentSelect = document.getElementById('paymentMethod');
            paymentSelect.innerHTML = '<option value="">نقدي</option>';
        });
}

function loadQuickItems() {
    fetch('/get_quick_items')
        .then(response => response.json())
        .then(items => {
            if (!Array.isArray(items)) {
                console.error('Expected array of items, got:', items);
                return;
            }

            const tbody = document.getElementById('quickItems');
            tbody.innerHTML = '';

            items.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.barcode}</td>
                    <td>${item.name}</td>
                    <td>${parseFloat(item.sell_price).toFixed(2)}</td>
                `;

                // Add click handler to add item to sales
                row.addEventListener('click', () => {
                    document.getElementById('barcodeInput').value = item.barcode;
                    // Trigger barcode input event
                    const event = new Event('input');
                    document.getElementById('barcodeInput').dispatchEvent(event);
                });

                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading quick items:', error);
            const tbody = document.getElementById('quickItems');
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: center; color: red;">
                        خطأ في تحميل العناصر السريعة
                    </td>
                </tr>
            `;
        });
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
    // Diagnostic log for debugging unexpected key events
    try { console.log('Global keydown:', { key: e.key, code: e.code, keyCode: e.keyCode }); } catch(err) {}
        // F1 for quantity editing
        if (e.key === 'F1') {
            e.preventDefault();
            const firstRow = document.querySelector('#salesItems tr:first-child');
            if (firstRow) {
                const quantityCell = firstRow.querySelector('.quantity-cell');
                quantityCell.focus();
                window.getSelection().selectAllChildren(quantityCell);

                quantityCell.addEventListener('keydown', function onEnter(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        quantityCell.removeEventListener('keydown', onEnter);
                        document.getElementById('barcodeInput').focus();
                    }
                });
            }
        }

        // F2 for previous table
        if (e.key === 'F3') {
            e.preventDefault();
            if (currentTableIndex > 1) {
                switchTable(currentTableIndex - 1);
                document.getElementById('barcodeInput').focus();
            }
        }

        // F3 for next table
        if (e.key === 'F2') {
            e.preventDefault();
            if (currentTableIndex < totalTables) {
                switchTable(currentTableIndex + 1);
                document.getElementById('barcodeInput').focus();
            }
        }

        // F5 for deleting last item
        if (e.key === 'F5') {
            e.preventDefault();
            const firstRow = document.querySelector('#salesItems tr:first-child');
            if (firstRow) {
                firstRow.remove();
                document.getElementById('barcodeInput').focus();
                updateTotals();
            }
        }
        // F9 for Print checkbox
        if (e.key === 'F9') {
            e.preventDefault();
            const printCheckbox = document.getElementById('printReceipt');
            printCheckbox.checked = !printCheckbox.checked;

            // Trigger change event to update table state
            const event = new Event('change');
            printCheckbox.dispatchEvent(event);

            // Return focus to barcode input
            document.getElementById('barcodeInput').focus();
        }
        // F10 for saving sale
        if (e.key === 'F10') {
            e.preventDefault();
            saveSale();
        }
        // F11 for printing last sale
        if (e.key === 'F11') {
            e.preventDefault();
            printLastSale();
        }

        // F12 for save and print
        if (e.key === 'F12') {
            e.preventDefault();
            saveAndPrint();
        }

        // Add F8 for paid amount focus
        if (e.key === 'F8') {
            e.preventDefault();
            const paidAmountInput = document.getElementById('paidAmount');
            paidAmountInput.focus();
            paidAmountInput.select();
        }
        // F7 for discount focus
        if (e.key === 'F7') {
            e.preventDefault();
            const discountInput = document.getElementById('discountAmount');
            discountInput.focus();
            discountInput.select();
        }

        // F8 for manual barcode mode toggle
        if (e.key === 'F8') {
            e.preventDefault();
            const checkbox = document.getElementById('manualBarcodeCheck');
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change'));
        }

    });
}


document.getElementById('discountAmount').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        document.getElementById('barcodeInput').focus();
    }
});
// Add these new functions
function saveAndPrint() {
    document.getElementById('printReceipt').checked = true;
    saveSale();
}

function printLastSale() {
    // First try to get the last sale ID from the server
    fetch('/get_last_sale_id')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.daily_sale_id) {
                return fetch('/print_last_receipt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
            } else {
                throw new Error('لا توجد فاتورة سابقة للطباعة');
            }
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                throw new Error(data.error || 'Failed to print receipt');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('حدث خطأ أثناء طباعة الفاتورة: ' + error);
        });
}



// Add event listeners for the new buttons
document.getElementById('savePrintReceipt').addEventListener('click', saveAndPrint);
document.getElementById('printLastReceipt').addEventListener('click', printLastSale);

function updateLastItemQuantity(quantity) {
    const displayElement = document.getElementById('lastItemQuantityDisplay');
    if (displayElement) {
        displayElement.textContent = parseFloat(quantity).toFixed(2);
    }
}

function addItemToSales(barcode) {
    fetch(`/get_item_Sell/${barcode}`)
        .then(response => response.json())
        .then(item => {
            if (item.error) {
                throw new Error(item.error);
            }

            const tbody = document.getElementById('salesItems');
            const existingRow = findExistingRowById(item.id);

            if (existingRow) {
                updateExistingRow(existingRow, item);
            } else {
                addNewRow(tbody, item);
            }
        })
        .catch(error => console.error('Error:', error));
}

function findExistingRowById(itemId) {
    if (!itemId && itemId !== 0) return null;
    const rows = document.querySelectorAll('#salesItems tr');
    for (let row of rows) {
        if (row.dataset && row.dataset.itemId && parseInt(row.dataset.itemId) === parseInt(itemId)) {
            return row;
        }
    }
    return null;
}

function updateExistingRow(row, item) {
    const currentQty = parseFloat(row.cells[2].textContent) || 0;
    const newQty = currentQty + 1;
    row.cells[2].textContent = newQty.toFixed(2);
    updateRowTotal(row, newQty, item.sell_price);
    updateTotals();
    updateLastItemQuantity(item.quantity);
}

function updateRowTotal(row, quantity, price) {
    const total = parseFloat(quantity) * parseFloat(price);
    row.cells[4].textContent = total.toFixed(2);
    updateTotals();
}

// Update the addNewRow function's quantity cell handlers
function addNewRow(tbody, item) {
    const row = document.createElement('tr');
    const total = parseFloat(item.sell_price);

    row.innerHTML = `
        <td>${item.barcode}</td>
        <td>${item.name}</td>
        <td contenteditable="true" class="quantity-cell">1.00</td>
        <td>${item.sell_price}</td>
        <td>${total.toFixed(2)}</td>
        <td>
            <button class="delete-btn" onclick="deleteRowItem(this)">
                <i class="fas fa-trash"></i>
            </button>
        </td>
    `;

    // Update quantity cell event listeners
    const quantityCell = row.querySelector('.quantity-cell');

    // Only handle Enter key and blur events
    quantityCell.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.blur();
            document.getElementById('barcodeInput').focus();
        }
    });

    // Format number only when losing focus
    quantityCell.addEventListener('blur', function() {
        let value = this.textContent.replace(/[^\d.]/g, '');
        const quantity = parseFloat(value) || 0;
        this.textContent = quantity.toFixed(2);
        updateRowTotal(row, quantity, item.sell_price);
        updateTotals();
        updateLastItemQuantity(quantity);
    });

    // attach item id for future matching (handles barcode2 matches)
    row.dataset.itemId = item.id;
    tbody.insertBefore(row, tbody.firstChild);
    updateTotals();
    updateLastItemQuantity(item.quantity);
}

function deleteRowItem(btn) {
    btn.closest('tr').remove();
    document.getElementById('barcodeInput').focus();
    updateTotals();
}



function showSearchResults(items) {
    let resultsDiv = document.getElementById('searchResults');
    if (!resultsDiv) {
        resultsDiv = document.createElement('div');
        resultsDiv.id = 'searchResults';
        document.querySelector('.form-group:nth-child(2)').appendChild(resultsDiv);
    }

    resultsDiv.innerHTML = items.map((item, index) => `
            <div class="search-item" data-barcode="${item.barcode}" data-index="${index}">
                ${item.name}
            </div>
        `).join('');

    // Initialize selection
    let selectedIndex = -1;
    const searchItems = resultsDiv.querySelectorAll('.search-item');

    // Add keyboard navigation
    document.getElementById('productName').addEventListener('keydown', function(e) {
        if (!searchItems.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, searchItems.length - 1);
            updateSelection();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, 0);
            updateSelection();
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
            e.preventDefault();
            const selectedItem = searchItems[selectedIndex];
            selectItem(selectedItem);
        }
    });

    // Add click handlers
    searchItems.forEach(div => {
        div.addEventListener('click', function() {
            selectItem(this);
        });
    });

    function updateSelection() {
        searchItems.forEach(item => item.classList.remove('selected'));
        if (selectedIndex >= 0) {
            searchItems[selectedIndex].classList.add('selected');
            searchItems[selectedIndex].scrollIntoView({
                block: 'nearest'
            });
        }
    }

    function selectItem(item) {
        const barcode = item.dataset.barcode;
        document.getElementById('productName').value = '';
        document.getElementById('barcodeInput').value = barcode;
        document.getElementById('barcodeInput').focus();
        hideSearchResults();
        // Trigger barcode input event
        const event = new Event('input');
        document.getElementById('barcodeInput').dispatchEvent(event);
    }
}

function hideSearchResults() {
    const resultsDiv = document.getElementById('searchResults');
    if (resultsDiv) {
        resultsDiv.innerHTML = '';
    }
}

// Add inside your existing script tag
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    let value = e.target.value;

    // Remove any non-numeric characters
    value = value.replace(/[^0-9]/g, '');

    // Ensure maximum length of 11
    if (value.length > 11) {
        value = value.slice(0, 11);
    }

    // Update input value
    e.target.value = value;
});


// Add keydown handler for paidAmount
document.getElementById('paidAmount').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const finalPrice = parseFloat(document.getElementById('finalPrice').textContent.replace(' ج.م', ''));
        const paidAmount = parseFloat(this.value) || 0;

        if (paidAmount < finalPrice) {
            alert('المبلغ المدفوع يجب أن يكون مساوياً أو أكبر من السعر النهائي');
            this.focus();
            return;
        }

        document.getElementById('barcodeInput').focus();
    }
});

// Add event listener for paid amount
document.getElementById('paidAmount').addEventListener('input', updateResidual);

function updateResidual() {
    const finalPrice = parseFloat(document.getElementById('finalPrice').textContent.replace(' ج.م', '')) || 0;
    const paidAmount = parseFloat(document.getElementById('paidAmount').value) || 0;
    const residual = paidAmount === 0 ? 0 : paidAmount - finalPrice;
    const residualElement = document.getElementById('residualAmount');

    residualElement.textContent = residual.toFixed(2) + ' ج.م';

    // Update color based on residual value
    if (paidAmount === 0) {
        residualElement.style.color = 'black';
    } else if (residual > 0) {
        residualElement.style.color = 'green';
    } else if (residual < 0) {
        residualElement.style.color = 'red';
    } else {
        residualElement.style.color = 'black';
    }
}

function saveCurrentTable() {
    const currentTable = salesTables[currentTableIndex - 1];

    // Save items
    currentTable.items = Array.from(document.querySelectorAll('#salesItems tr')).map(row => ({
        barcode: row.cells[0].textContent,
        name: row.cells[1].textContent,
        quantity: parseInt(row.cells[2].textContent),
        price: parseFloat(row.cells[3].textContent),
        total: parseFloat(row.cells[4].textContent)
    }));

    // Save delivery info
    currentTable.delivery = {
        phone: document.getElementById('phoneNumber').value,
        name: document.getElementById('customerName').value,
        address1: document.getElementById('addressLine1').value,
        address2: document.getElementById('addressLine2').value,
        address3: document.getElementById('addressLine3').value,
        service: document.getElementById('deliveryService').value
    };

    // Save discount and payment
    currentTable.discount = document.getElementById('discountAmount').value;
    currentTable.payment = document.getElementById('paymentMethod').value;

    // Save print state
    currentTable.print = document.getElementById('printReceipt').checked;
}

function loadTable(index) {
    const table = salesTables[index - 1];
    const tbody = document.getElementById('salesItems');

    // Clear current table
    tbody.innerHTML = '';

    // Load items
    table.items.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.barcode}</td>
            <td>${item.name}</td>
            <td contenteditable="true" class="quantity-cell">${item.quantity}</td>
            <td>${item.price}</td>
            <td>${item.total.toFixed(2)}</td>
            <td>
                <button class="delete-btn" onclick="deleteRowItem(this)">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });

    // Load delivery info
    document.getElementById('phoneNumber').value = table.delivery.phone;
    document.getElementById('customerName').value = table.delivery.name;
    document.getElementById('addressLine1').value = table.delivery.address1;
    document.getElementById('addressLine2').value = table.delivery.address2;
    document.getElementById('addressLine3').value = table.delivery.address3;
    document.getElementById('deliveryService').value = table.delivery.service;

    // Load discount and payment
    document.getElementById('discountAmount').value = table.discount;
    document.getElementById('paymentMethod').value = table.payment;

    // Load print state
    document.getElementById('printReceipt').checked = table.print;
    document.getElementById('printReceipt').dataset.table = index;

    // Update totals
    updateTotals();

    // Update navigation
    document.getElementById('currentTable').textContent = index;
    document.getElementById('prevTable').disabled = index === 1;
    document.getElementById('nextTable').disabled = index === totalTables;
}

function switchTable(newIndex) {
    if (newIndex < 1 || newIndex > totalTables) return;

    saveCurrentTable();
    currentTableIndex = newIndex;
    loadTable(currentTableIndex);

}

// Add print checkbox change handler
document.getElementById('printReceipt').addEventListener('change', function(e) {
    const tableIndex = parseInt(this.dataset.table) - 1;
    salesTables[tableIndex].print = this.checked;
    document.getElementById('barcodeInput').focus();
});

// Add after your existing event listeners

document.getElementById('saveReceipt').addEventListener('click', function() {
    console.log('saveReceipt clicked');
    saveSale();
});

function saveSale() {
    console.log('saveSale invoked', new Date().toISOString());
    // Defensive guard: if saveSale is called very shortly after completing
    // entering a phone number, ignore it. This prevents accidental saves
    // caused by a stray key event when the user finishes typing the 11th digit.
    try {
        if (lastPhoneCompletedAt && (Date.now() - lastPhoneCompletedAt) < PHONE_COMPLETE_BLOCK_MS) {
            console.log('saveSale blocked: recent phone completion (ms since):', Date.now() - lastPhoneCompletedAt);
            // reset the marker so subsequent saves are allowed
            lastPhoneCompletedAt = 0;
            return;
        }
    } catch (err) {
        console.warn('Error checking phone completion guard:', err);
    }
    const phoneNumber = document.getElementById('phoneNumber').value;
    const deliveryService = document.getElementById('deliveryService').value;
    
    // Check if phone exists but no delivery fee
    if (phoneNumber.length === 11 && (!deliveryService || deliveryService === '0')) {
        // Non-blocking inline message instead of alert
        showInlineMessage(document.getElementById('deliveryService'), 'يجب إدخال رسوم التوصيل للطلبات مع رقم الهاتف');
        const ds = document.getElementById('deliveryService');
        if (ds) ds.focus();
        return;
    }
    
    // Get all items from the current table
    const tbody = document.getElementById('salesItems');
    const rows = tbody.getElementsByTagName('tr');

    if (rows.length === 0) {
        alert('لا يمكن حفظ فاتورة فارغة');
        return;
    }

    // Get totals from the display
    const totalPrice = parseFloat(document.getElementById('totalPrice').textContent.replace(' ج.م', ''));
    const finalPrice = parseFloat(document.getElementById('finalPrice').textContent.replace(' ج.م', ''));
    const discount = parseFloat(document.getElementById('discountAmount').value || 0);
    const deliveryFee = parseFloat(deliveryService || 0);  // Use deliveryService value
    const paidAmount = parseFloat(document.getElementById('paidAmount').value) || 0;
    const residual = paidAmount - finalPrice;
    
    // Get selected cash box ID
    const cashBoxId = document.getElementById('paymentMethod').value;

    // Prepare sale data
    const saleData = {
        items: Array.from(rows).map(row => ({
            barcode: row.cells[0].textContent,
            name: row.cells[1].textContent,
            quantity: parseFloat(row.cells[2].textContent),
            unit_price: parseFloat(row.cells[3].textContent),
            total_price: parseFloat(row.cells[4].textContent)
        })),
        total_amount: totalPrice,
        subtotal: totalPrice,
        discount_amount: discount,
        delivery_fee: deliveryFee,  // Use the same deliveryFee variable
        final_amount: finalPrice,
        paid_amount: paidAmount,
        residual: residual,
        payment_method: document.getElementById('paymentMethod').options[document.getElementById('paymentMethod').selectedIndex].text,
        cash_box_id: parseInt(cashBoxId),
        customer_name: document.getElementById('customerName').value,
        customer_phone: phoneNumber,
        address_line1: document.getElementById('addressLine1').value,
        address_line2: document.getElementById('addressLine2').value,
        address_line3: document.getElementById('addressLine3').value,
        print: document.getElementById('printReceipt').checked
    };

    console.log('Sending sale data:', saleData);

    fetch('/save_sale', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(saleData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => Promise.reject(data.error || 'Failed to save sale'));
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                lastSaleId = data.daily_sale_id; // Store the last sale ID
                clearTable();
                if (saleData.print && data.daily_sale_id) {
                    return fetch(`/print_receipt/${data.daily_sale_id}`);
                }
            } else {
                throw new Error(data.error || 'Failed to save sale');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('حدث خطأ أثناء حفظ الفاتورة: ' + error);
        });
}

function clearCurrentTable() {
    salesTables[currentTableIndex - 1] = {
        items: [],
        total: 0,
        subtotal: 0,
        discount: 0,
        final: 0
    };
    updateTableDisplay();
}


// Update the clearTable function to include clearing paid amount
function clearTable() {
    // Clear sales items
    document.getElementById('salesItems').innerHTML = '';

    // Clear delivery info
    document.getElementById('phoneNumber').value = '';
    document.getElementById('customerName').value = '';
    document.getElementById('addressLine1').value = '';
    document.getElementById('addressLine2').value = '';
    document.getElementById('addressLine3').value = '';
    document.getElementById('deliveryService').value = '';

    // Reset totals
    document.getElementById('discountAmount').value = '0';
    
    // Reset payment method to نقدي (cash box)
    const paymentSelect = document.getElementById('paymentMethod');
    const nakdiOption = Array.from(paymentSelect.options).find(opt => opt.textContent === 'نقدي');
    if (nakdiOption) {
        paymentSelect.value = nakdiOption.value;
    } else if (paymentSelect.options.length > 0) {
        paymentSelect.selectedIndex = 0;
    }
    
    document.getElementById('printReceipt').checked = false;
    document.getElementById('paidAmount').value = '0';
    document.getElementById('residualAmount').textContent = '0.00 ج.م';

    // Clear current table data in salesTables array
    salesTables[currentTableIndex - 1] = {
        items: [],
        delivery: {
            phone: '',
            name: '',
            address1: '',
            address2: '',
            address3: '',
            service: ''
        },
        discount: 0,
        payment: paymentSelect.value,
        print: false
    };

    // Update totals display
    updateTotals();

    // Focus on barcode input
    document.getElementById('barcodeInput').focus();
    updateDeliveryServiceState();
}

function updateDeliveryServiceState() {
    const phoneNumber = document.getElementById('phoneNumber').value.trim();
    const deliveryService = document.getElementById('deliveryService');
    const addressInputs = [
        document.getElementById('addressLine1'),
        document.getElementById('addressLine2'),
        document.getElementById('addressLine3')
    ];
    const customerNameInput = document.getElementById('customerName'); // Add this line


    if (!phoneNumber) {
        // If phone is empty, disable and clear delivery service
        deliveryService.value = '';
        deliveryService.disabled = true;
        
        // Clear and disable address inputs
        addressInputs.forEach(input => {
            input.value = '';
            input.disabled = true;
        });
        customerNameInput.value = ''; // Add this line to clear customer name

    } else {
        // If phone has value, enable delivery service and address inputs
        deliveryService.disabled = false;
        addressInputs.forEach(input => {
            input.disabled = false;
        });
    }

    // Update totals to reflect any changes
    updateTotals();
}

// Update the phone number event listener
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    let value = e.target.value.replace(/[^0-9]/g, '').slice(0, PHONE_LENGTH);

    // Update input value
    this.value = value;

    // Hide suggestions immediately if number complete
    if (value.length === PHONE_LENGTH) {
        hidePhoneSuggestions();
        loadCustomerData(value);
        // focus customer name and select
        setTimeout(() => { const nm = document.getElementById('customerName'); if (nm) { nm.focus(); nm.select(); } }, 50);
    } else if (value.length >= 3) {
        // show suggestions
        fetch(`/get_phone_suggestions/${value}`)
            .then(response => response.json())
            .then(data => { if (data.suggestions) showPhoneSuggestions(data.suggestions); })
            .catch(err => console.error('Error fetching suggestions:', err));
    } else {
        hidePhoneSuggestions();
    }

    // Update delivery service state whenever phone changes
    updateDeliveryServiceState();
});

// Add event listener for when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize delivery service state
    updateDeliveryServiceState();

    // Rest of your existing DOMContentLoaded code...
});

// Add to your existing script section
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    let value = e.target.value;
    value = value.replace(/[^0-9]/g, '');

    if (value.length > 11) {
        value = value.slice(0, 11);
    }

    // Update input value
    this.value = value;

    // Show suggestions if we have at least 3 digits
    if (value.length >= 3) {
        console.log('Fetching suggestions for:', value);

        // Use the centralized showPhoneSuggestions so we have only one container
        fetch(`/get_phone_suggestions/${value}`)
            .then(response => response.json())
            .then(data => {
                if (data.suggestions && data.suggestions.length > 0) {
                    showPhoneSuggestions(data.suggestions);
                } else {
                    hidePhoneSuggestions();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                hidePhoneSuggestions();
            });
    } else {
        hidePhoneSuggestions();
    }

    // Load customer data if number is complete
    if (value.length === 11) {
        loadCustomerData(value);
    }
});

function showPhoneSuggestions(suggestions) {
    let container = document.getElementById('phoneSuggestions');
    // If the container is not present in the DOM (some templates may not include it),
    // create a lightweight container next to the phone input so code can safely use it.
    if (!container) {
        try {
            const phoneInput = document.getElementById('phoneNumber');
            container = document.createElement('div');
            container.id = 'phoneSuggestions';
            container.className = 'phone-suggestions';
            if (phoneInput && phoneInput.parentElement) {
                phoneInput.parentElement.appendChild(container);
            } else {
                // Fallback to appending to body if phone input isn't found
                document.body.appendChild(container);
            }
            console.warn('phoneSuggestions container was missing; created a fallback container');
        } catch (err) {
            console.error('Failed to create phoneSuggestions container:', err);
            return; // cannot safely show suggestions
        }
    }
    const phoneVal = (document.getElementById('phoneNumber') || { value: '' }).value.replace(/[^0-9]/g, '');

    // If the phone input is complete, don't show suggestions
    if (phoneVal.length === PHONE_LENGTH) {
        return hidePhoneSuggestions();
    }

    if (!suggestions || suggestions.length === 0) {
        return hidePhoneSuggestions();
    }

    container.innerHTML = suggestions.map(phone => `
        <div class="suggestion-item" data-phone="${phone}">
            ${phone}
        </div>
    `).join('');

    container.style.display = 'block';

    // Add click handlers
    container.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', function() {
            document.getElementById('phoneNumber').value = this.dataset.phone;
            hidePhoneSuggestions();
            if (this.dataset.phone.length === PHONE_LENGTH) {
                loadCustomerData(this.dataset.phone);
                setTimeout(() => {
                    const nameEl = document.getElementById('customerName');
                    if (nameEl) { nameEl.focus(); nameEl.select(); }
                }, 50);
            }
        });
    });
}

function hidePhoneSuggestions() {
    const container1 = document.getElementById('phoneSuggestions');
    if (container1) container1.style.display = 'none';
}



// Add phone number input listener
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    const phone = this.value;
    if (phone.length >= 11) {
        loadCustomerData(phone);
    } else {
        document.querySelector('.customer-history-section').style.display = 'none';
    }
});
// Add event listener for customer history button
function showCustomerHistory() {
    const phone = document.getElementById('phoneNumber').value;
    if (!phone) {
        alert('الرجاء إدخال رقم الهاتف');
        return;
    }

    // Show loading state
    const modal = document.getElementById('orderHistoryModal');
    const tableBody = document.getElementById('orderHistoryTable');
    
    // Debug logs
    console.log('Fetching history for phone:', phone);
    
    // Show the modal first
    modal.style.display = 'block';
    modal.classList.add('show');
    
    // Show loading indicator
    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">جاري التحميل...</td></tr>';

    fetch(`/get_customer_history/${phone}`)
        .then(response => response.json())
        .then(data => {
            console.log('Received customer data:', data); // Debug log
            
            if (data.success) {
                // Update customer info
                document.getElementById('customerInfoDetails').innerHTML = `
                    <div class="row">
                        <div class="col">
                            <strong>الاسم:</strong> ${data.customer.name || 'غير محدد'}<br>
                            <strong>الهاتف:</strong> ${data.customer.phone || phone}<br>
                            <strong>العنوان:</strong> 
                            ${data.customer.address_line1 || ''} 
                            ${data.customer.address_line2 || ''} 
                            ${data.customer.address_line3 || ''}
                        </div>
                    </div>
                `;

                // Update orders table
                if (data.orders && data.orders.length > 0) {
                    console.log('Rendering orders:', data.orders); // Debug log
                    tableBody.innerHTML = data.orders.map(order => {
                        // prefer delivery worker name fields from different sources
                        const dw = order.delivery_worker_name || order.delivery_worker || order.delivery_worker_name2 || order.delivery_worker_name_from_daily || '';
                        return `
                        <tr>
                            <td>${order.sale_number || ''}</td>
                            <td>${order.created_at ? new Date(order.created_at).toLocaleString('ar-EG') : ''}</td>
                            <td>${order.final_amount ? order.final_amount.toFixed(2) : '0.00'} ج.م</td>
                            <td>${order.address_line1 || ''}</td>
                            <td>${dw}</td>
                            <td>${order.status || 'مكتمل'}</td>
                            <td>
                                <button class="btn btn-sm btn-info" onclick="viewOrderDetails(${order.id})">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </td>
                        </tr>
                    `}).join('');
                } else {
                    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">لا توجد طلبات سابقة</td></tr>';
                }
            } else {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center text-danger">
                            ${data.error || 'لا توجد بيانات متاحة'}
                        </td>
                    </tr>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching customer history:', error);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-danger">
                        حدث خطأ أثناء تحميل البيانات: ${error.message}
                    </td>
                </tr>
            `;
        });
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Show customer history button handler
    const historyBtn = document.getElementById('showCustomerHistory');
    if (historyBtn) {
        historyBtn.addEventListener('click', showCustomerHistory);
        console.log('History button handler attached'); // Debug log
    }

    // Close button handler
    const closeBtn = document.querySelector('.modal .close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            const modal = document.getElementById('orderHistoryModal');
            modal.style.display = 'none';
            modal.classList.remove('show');
        });
    }
});
// Clear customer history section when phone is cleared
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    if (!this.value) {
        document.querySelector('.customer-history-section').style.display = 'none';
    }
});

// Close on outside click
window.onclick = function(event) {
    const modal = document.getElementById('customerHistoryModal');
    if (event.target === modal) {
        modal.classList.remove('show');
    }
}

/* filepath: /e:/Market/static/js/home.js */
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    let value = e.target.value;
    console.log('Input value:', value); // Debug log

    if (value.length >= 3) {
        console.log('Fetching suggestions for:', value); // Debug log
        fetch(`/get_phone_suggestions/${value}`)
            .then(response => {
                console.log('Response:', response); // Debug log
                return response.json();
            })
            .then(data => {
                console.log('Suggestions data:', data); // Debug log
                showPhoneSuggestions(data.suggestions);
            })
            .catch(error => console.error('Error:', error));
        }
        else if(value.lenght == 11) 
        {
            hidePhoneSuggestions();
        }
    });


function submitSale() {
    // Gather sale data
    const saleData = {
        total_amount: parseFloat(document.getElementById('totalAmount').value),
        subtotal: parseFloat(document.getElementById('subtotal').value),
        discount_amount: parseFloat(document.getElementById('discountAmount').value || 0),
        delivery_fee: parseFloat(document.getElementById('deliveryService').value || 0),
        final_amount: parseFloat(document.getElementById('finalAmount').value),
        payment_method: 'cash',
        customer_name: document.getElementById('customerName').value,
        customer_phone: document.getElementById('phoneNumber').value,
        address_line1: document.getElementById('addressLine1').value,
        address_line2: document.getElementById('addressLine2').value,
        address_line3: document.getElementById('addressLine3').value,
        items: [] // Add your items here
    };

    console.log('Submitting sale:', saleData);
    saveSale(saleData);
}

// Add event listener for discount changes
document.getElementById('discountAmount').addEventListener('input', updateTotals);
document.getElementById('deliveryService').addEventListener('change', updateTotals);

// Update the updateTotals function
function updateTotals() {
    const rows = document.querySelectorAll('#salesItems tr');
    let totalQuantity = 0;
    let totalPrice = 0;

    rows.forEach(row => {
        totalQuantity += parseFloat(row.cells[2].textContent) || 0;
        totalPrice += parseFloat(row.cells[4].textContent) || 0;
    });

    const discount = parseFloat(document.getElementById('discountAmount').value) || 0;
    const deliveryCost = parseFloat(document.getElementById('deliveryService').value) || 0;
    const finalPrice = totalPrice - discount + deliveryCost;
    const paidAmount = parseFloat(document.getElementById('paidAmount').value) || 0;

    // Update display values
    document.getElementById('totalQuantity').textContent = totalQuantity.toFixed(2);
    document.getElementById('totalPrice').textContent = totalPrice.toFixed(2) + ' ج.م';
    document.getElementById('finalPrice').textContent = finalPrice.toFixed(2) + ' ج.م';

    // Update residual with conditional logic
    const residual = paidAmount === 0 ? 0 : paidAmount - finalPrice;
    const residualElement = document.getElementById('residualAmount');
    residualElement.textContent = residual.toFixed(2) + ' ج.م';

    // Update color based on residual and paid amount
    if (paidAmount === 0) {
        residualElement.style.color = 'black';
        residualElement.textContent = '0.00 ج.م';
    } else if (residual > 0) {
        residualElement.style.color = 'green';
    } else if (residual < 0) {
        residualElement.style.color = 'red';
    } else {
        residualElement.style.color = 'black';
    }
}

// Update discount input validation
document.getElementById('discountAmount').addEventListener('input', function(e) {
    const totalPrice = parseFloat(document.getElementById('totalPrice').textContent.replace(' ج.م', ''));
    const discount = parseFloat(this.value) || 0;

    if (discount > totalPrice) {
        alert('الخصم لا يمكن أن يكون أكبر من إجمالي السعر');
        this.value = '0';
        updateTotals();
    }
});



// Add these event listeners
document.addEventListener('DOMContentLoaded', function() {
    // History modal close button
    const historyCloseBtn = document.querySelector('#orderHistoryModal .close');
    if (historyCloseBtn) {
        historyCloseBtn.addEventListener('click', function() {
            const historyModal = document.getElementById('orderHistoryModal');
            historyModal.classList.remove('show');
        });
    }

    // History modal outside click
    const historyModal = document.getElementById('orderHistoryModal');
    if (historyModal) {
        historyModal.addEventListener('click', function(event) {
            if (event.target === historyModal) {
                historyModal.classList.remove('show');
            }
        });
    }

    // History button handler
    const historyBtn = document.getElementById('showCustomerHistory');
    if (historyBtn) {
        historyBtn.addEventListener('click', showCustomerHistory);
    }
});

function viewOrderDetails(orderId) {
    if (!orderId) {
        console.error('No order ID provided');
        return;
    }

    fetch(`/get_order_details/${orderId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Create and show a new modal for order details
                let detailsModal = document.getElementById('orderDetailsModal');
                
                // If modal doesn't exist, create it
                if (!detailsModal) {
                    detailsModal = document.createElement('div');
                    detailsModal.id = 'orderDetailsModal';
                    detailsModal.className = 'modal';
                    detailsModal.innerHTML = `
                        <div class="modal-dialog modal-lg">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">تفاصيل الطلب #${data.order.sale_number}</h5>
                                    <button type="button" class="close" onclick="closeOrderDetails()">
                                        <span>&times;</span>
                                    </button>
                                </div>
                                <div class="modal-body">
                                    <div class="order-info mb-3">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <p><strong>التاريخ:</strong> ${new Date(data.order.created_at).toLocaleString('ar-EG')}</p>
                                                <p><strong>العميل:</strong> ${data.order.customer_name || 'غير محدد'}</p>
                                                <p><strong>الهاتف:</strong> ${data.order.customer_phone || ''}</p>
                                            </div>
                                            <div class="col-md-6">
                                                <p><strong>الحالة:</strong> ${data.order.status || 'مكتمل'}</p>
                                                <p><strong>طريقة الدفع:</strong> ${data.order.payment_method || 'نقدي'}</p>
                                                <p><strong>العنوان:</strong> ${data.order.address_line1 || ''}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="table-responsive">
                                        <table class="table table-bordered">
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
                                                        <td>${item.name}</td>
                                                        <td>${item.quantity}</td>
                                                        <td>${item.unit_price.toFixed(2)} ج.م</td>
                                                        <td>${item.total_price.toFixed(2)} ج.م</td>
                                                    </tr>
                                                `).join('')}
                                            </tbody>
                                            <tfoot>
                                                <tr>
                                                    <td colspan="3" class="text-left"><strong>الإجمالي:</strong></td>
                                                    <td>${data.order.total_amount.toFixed(2)} ج.م</td>
                                                </tr>
                                                ${data.order.discount_amount ? `
                                                    <tr>
                                                        <td colspan="3" class="text-left"><strong>الخصم:</strong></td>
                                                        <td>${data.order.discount_amount.toFixed(2)} ج.م</td>
                                                    </tr>
                                                ` : ''}
                                                ${data.order.delivery_fee ? `
                                                    <tr>
                                                        <td colspan="3" class="text-left"><strong>خدمة التوصيل:</strong></td>
                                                        <td>${data.order.delivery_fee.toFixed(2)} ج.م</td>
                                                    </tr>
                                                ` : ''}
                                                <tr>
                                                    <td colspan="3" class="text-left"><strong>المبلغ النهائي:</strong></td>
                                                    <td>${data.order.final_amount.toFixed(2)} ج.م</td>
                                                </tr>
                                            </tfoot>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(detailsModal);
                }

                // Show the modal
                detailsModal.style.display = 'block';
                detailsModal.classList.add('show');
            } else {
                alert('لا يمكن تحميل تفاصيل الطلب');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('حدث خطأ أثناء تحميل تفاصيل الطلب');
        });
}

function closeOrderDetails() {
    const modal = document.getElementById('orderDetailsModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('show');
    }
}

// Update the phone number input event listener
document.getElementById('phoneNumber').addEventListener('input', function(e) {
    let value = e.target.value.trim();
    
    // Remove non-numeric characters
    value = value.replace(/[^0-9]/g, '');
    
    // Limit to 11 digits
    if (value.length > 11) {
        value = value.slice(0, 11);
    }
    
    // Update input value
    this.value = value;

    // Show/hide suggestions based on input length
    if (value.length >= 3 && value.length < 11) {
        fetch(`/get_phone_suggestions/${value}`)
            .then(response => response.json())
            .then(data => {
                showPhoneSuggestions(data.suggestions);
            })
            .catch(error => console.error('Error:', error));
    } else {
        hidePhoneSuggestions();
    }

    // If phone number is complete (11 digits)
    if (value.length === 11) {
        hidePhoneSuggestions(); // Hide suggestions immediately
        loadCustomerData(value);
        
        // Make delivery fee required
        const deliveryService = document.getElementById('deliveryService');
        deliveryService.required = true;
        
        // Focus on customer name after a short delay
        setTimeout(() => {
            document.getElementById('customerName').focus();
            if (!deliveryService.value) {
                // Non-blocking inline message instead of alert
                showInlineMessage(deliveryService, 'يجب إدخال رسوم التوصيل');
                deliveryService.focus();
            }
            // schedule auto-save in case user already filled name/address
            scheduleAutoSaveCustomer();
        }, 100);
    } else {
        // Make delivery fee optional
        document.getElementById('deliveryService').required = false;
    }
});

// Update loadCustomerData to focus on customer name if empty
function loadCustomerData(phone) {
    if (!phone) return;

    fetch(`/get_customer_data/${phone}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Fill customer data
                const customerNameInput = document.getElementById('customerName');
                customerNameInput.value = data.customer.name || '';
                document.getElementById('addressLine1').value = data.customer.address_line1 || '';
                document.getElementById('addressLine2').value = data.customer.address_line2 || '';
                document.getElementById('addressLine3').value = data.customer.address_line3 || '';

                // Show customer history section
                document.querySelector('.customer-history-section').style.display = 'block';
                
                // Focus on customer name if it's empty
                if (!data.customer.name) {
                    customerNameInput.focus();
                }
            }
        })
        .catch(error => console.error('Error:', error));
}

// Add this CSS to your styles
const style = document.createElement('style');
style.textContent = `
    .manual-barcode-control {
        margin: 10px 0;
    }
    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
    }
    .checkbox-label input[type="checkbox"] {
        cursor: pointer;
    }
`;
document.head.appendChild(style);

