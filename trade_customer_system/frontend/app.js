const API_BASE_URL = 'http://localhost:5000/api';

let currentUser = null;
let currentToken = null;

function getAuthHeaders() {
    return { 'Authorization': `Bearer ${currentToken}` };
}

async function login(email, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (response.ok) {
            currentUser = data.user;
            currentToken = data.access_token;
            localStorage.setItem('token', currentToken);
            localStorage.setItem('user', JSON.stringify(currentUser));
            return true;
        }
        return false;
    } catch (error) {
        console.error('Login error:', error);
        return false;
    }
}

function logout() {
    currentUser = null;
    currentToken = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    document.getElementById('login-screen').classList.add('active');
    document.getElementById('main-screen').classList.remove('active');
}

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));
    document.getElementById(`${viewId}-view`).classList.add('active');
    document.querySelector(`[data-view="${viewId}"]`).classList.add('active');
}

async function loadCustomers() {
    try {
        const search = document.getElementById('customer-search').value;
        const status = document.getElementById('customer-status-filter').value;
        const response = await fetch(`${API_BASE_URL}/customers?search=${search}&status=${status}`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();
        const tbody = document.getElementById('customers-table').querySelector('tbody');
        tbody.innerHTML = data.items.map(customer => `
            <tr>
                <td>${customer.company_name}</td>
                <td>${customer.contact_person || '-'}</td>
                <td>${customer.email || '-'}</td>
                <td>${customer.country || '-'}</td>
                <td><span class="status-badge status-${customer.status}">${getStatusText(customer.status)}</span></td>
                <td>${customer.rating}★</td>
                <td>
                    <button class="btn btn-edit" onclick="editCustomer(${customer.id})">编辑</button>
                    <button class="btn btn-delete" onclick="deleteCustomer(${customer.id})">删除</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load customers error:', error);
    }
}

function getStatusText(status) {
    const statusMap = {
        'potential': '潜在客户',
        'contacted': '已联系',
        'negotiating': '洽谈中',
        'converted': '已成交',
        'pending': '待处理',
        'replied': '已回复',
        'closed': '已关闭',
        'in_progress': '进行中',
        'completed': '已完成'
    };
    return statusMap[status] || status;
}

async function addCustomer() {
    const formHtml = `
        <div class="form-group">
            <label>公司名称 *</label>
            <input type="text" name="company_name" required>
        </div>
        <div class="form-group">
            <label>联系人</label>
            <input type="text" name="contact_person">
        </div>
        <div class="form-group">
            <label>邮箱</label>
            <input type="email" name="email">
        </div>
        <div class="form-group">
            <label>电话</label>
            <input type="text" name="phone">
        </div>
        <div class="form-group">
            <label>国家</label>
            <input type="text" name="country">
        </div>
        <div class="form-group">
            <label>城市</label>
            <input type="text" name="city">
        </div>
        <div class="form-group">
            <label>行业</label>
            <input type="text" name="industry">
        </div>
        <div class="form-group">
            <label>网站</label>
            <input type="url" name="website">
        </div>
        <div class="form-group">
            <label>来源</label>
            <input type="text" name="source">
        </div>
        <div class="form-group">
            <label>状态</label>
            <select name="status">
                <option value="potential">潜在客户</option>
                <option value="contacted">已联系</option>
                <option value="negotiating">洽谈中</option>
                <option value="converted">已成交</option>
            </select>
        </div>
        <div class="form-group">
            <label>评分</label>
            <input type="number" name="rating" min="0" max="5" value="0">
        </div>
        <div class="form-group">
            <label>备注</label>
            <textarea name="notes"></textarea>
        </div>
    `;
    openModal('添加客户', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/customers`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadCustomers();
    });
}

async function editCustomer(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/customers/${id}`, { headers: getAuthHeaders() });
        const customer = await response.json();
        const formHtml = `
            <input type="hidden" name="id" value="${customer.id}">
            <div class="form-group">
                <label>公司名称 *</label>
                <input type="text" name="company_name" value="${customer.company_name}" required>
            </div>
            <div class="form-group">
                <label>联系人</label>
                <input type="text" name="contact_person" value="${customer.contact_person || ''}">
            </div>
            <div class="form-group">
                <label>邮箱</label>
                <input type="email" name="email" value="${customer.email || ''}">
            </div>
            <div class="form-group">
                <label>电话</label>
                <input type="text" name="phone" value="${customer.phone || ''}">
            </div>
            <div class="form-group">
                <label>国家</label>
                <input type="text" name="country" value="${customer.country || ''}">
            </div>
            <div class="form-group">
                <label>城市</label>
                <input type="text" name="city" value="${customer.city || ''}">
            </div>
            <div class="form-group">
                <label>行业</label>
                <input type="text" name="industry" value="${customer.industry || ''}">
            </div>
            <div class="form-group">
                <label>网站</label>
                <input type="url" name="website" value="${customer.website || ''}">
            </div>
            <div class="form-group">
                <label>来源</label>
                <input type="text" name="source" value="${customer.source || ''}">
            </div>
            <div class="form-group">
                <label>状态</label>
                <select name="status">
                    <option value="potential" ${customer.status === 'potential' ? 'selected' : ''}>潜在客户</option>
                    <option value="contacted" ${customer.status === 'contacted' ? 'selected' : ''}>已联系</option>
                    <option value="negotiating" ${customer.status === 'negotiating' ? 'selected' : ''}>洽谈中</option>
                    <option value="converted" ${customer.status === 'converted' ? 'selected' : ''}>已成交</option>
                </select>
            </div>
            <div class="form-group">
                <label>评分</label>
                <input type="number" name="rating" min="0" max="5" value="${customer.rating}">
            </div>
            <div class="form-group">
                <label>备注</label>
                <textarea name="notes">${customer.notes || ''}</textarea>
            </div>
        `;
        openModal('编辑客户', formHtml, async (data) => {
            const id = data.id;
            delete data.id;
            await fetch(`${API_BASE_URL}/customers/${id}`, {
                method: 'PUT',
                headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            loadCustomers();
        });
    } catch (error) {
        console.error('Edit customer error:', error);
    }
}

async function deleteCustomer(id) {
    if (confirm('确定要删除这个客户吗？')) {
        await fetch(`${API_BASE_URL}/customers/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        loadCustomers();
    }
}

async function loadInquiries() {
    try {
        const status = document.getElementById('inquiry-status-filter').value;
        const response = await fetch(`${API_BASE_URL}/inquiries?status=${status}`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();
        const tbody = document.getElementById('inquiries-table').querySelector('tbody');
        tbody.innerHTML = data.items.map(inquiry => `
            <tr>
                <td>${inquiry.subject}</td>
                <td>${inquiry.customer_name}</td>
                <td>${inquiry.product_name || '-'}</td>
                <td>${inquiry.quantity || '-'}</td>
                <td>${inquiry.budget ? `${inquiry.currency} ${inquiry.budget}` : '-'}</td>
                <td><span class="status-badge status-${inquiry.status}">${getStatusText(inquiry.status)}</span></td>
                <td><span class="priority-${inquiry.priority}">${getPriorityText(inquiry.priority)}</span></td>
                <td>
                    <button class="btn btn-edit" onclick="editInquiry(${inquiry.id})">编辑</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load inquiries error:', error);
    }
}

function getPriorityText(priority) {
    const priorityMap = { 'high': '高', 'normal': '中', 'low': '低' };
    return priorityMap[priority] || priority;
}

async function addInquiry() {
    const customers = await fetchCustomers();
    const products = await fetchProducts();
    const formHtml = `
        <div class="form-group">
            <label>客户 *</label>
            <select name="customer_id" required>
                ${customers.map(c => `<option value="${c.id}">${c.company_name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>产品</label>
            <select name="product_id">
                <option value="">选择产品</option>
                ${products.map(p => `<option value="${p.id}">${p.product_name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>主题 *</label>
            <input type="text" name="subject" required>
        </div>
        <div class="form-group">
            <label>内容</label>
            <textarea name="content"></textarea>
        </div>
        <div class="form-group">
            <label>数量</label>
            <input type="number" name="quantity" min="1">
        </div>
        <div class="form-group">
            <label>预算</label>
            <input type="number" name="budget" min="0">
        </div>
        <div class="form-group">
            <label>货币</label>
            <select name="currency">
                <option value="USD">USD</option>
                <option value="CNY">CNY</option>
                <option value="EUR">EUR</option>
            </select>
        </div>
        <div class="form-group">
            <label>状态</label>
            <select name="status">
                <option value="pending">待处理</option>
                <option value="replied">已回复</option>
                <option value="negotiating">洽谈中</option>
                <option value="closed">已关闭</option>
            </select>
        </div>
        <div class="form-group">
            <label>优先级</label>
            <select name="priority">
                <option value="high">高</option>
                <option value="normal" selected>中</option>
                <option value="low">低</option>
            </select>
        </div>
        <div class="form-group">
            <label>来源</label>
            <input type="text" name="source">
        </div>
    `;
    openModal('添加询盘', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/inquiries`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadInquiries();
    });
}

async function editInquiry(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/inquiries/${id}`, { headers: getAuthHeaders() });
        const inquiry = await response.json();
        const customers = await fetchCustomers();
        const products = await fetchProducts();
        const formHtml = `
            <input type="hidden" name="id" value="${inquiry.id}">
            <div class="form-group">
                <label>状态</label>
                <select name="status">
                    <option value="pending" ${inquiry.status === 'pending' ? 'selected' : ''}>待处理</option>
                    <option value="replied" ${inquiry.status === 'replied' ? 'selected' : ''}>已回复</option>
                    <option value="negotiating" ${inquiry.status === 'negotiating' ? 'selected' : ''}>洽谈中</option>
                    <option value="closed" ${inquiry.status === 'closed' ? 'selected' : ''}>已关闭</option>
                </select>
            </div>
            <div class="form-group">
                <label>优先级</label>
                <select name="priority">
                    <option value="high" ${inquiry.priority === 'high' ? 'selected' : ''}>高</option>
                    <option value="normal" ${inquiry.priority === 'normal' ? 'selected' : ''}>中</option>
                    <option value="low" ${inquiry.priority === 'low' ? 'selected' : ''}>低</option>
                </select>
            </div>
        `;
        openModal('编辑询盘', formHtml, async (data) => {
            const id = data.id;
            delete data.id;
            await fetch(`${API_BASE_URL}/inquiries/${id}`, {
                method: 'PUT',
                headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            loadInquiries();
        });
    } catch (error) {
        console.error('Edit inquiry error:', error);
    }
}

async function fetchCustomers() {
    const response = await fetch(`${API_BASE_URL}/customers`, { headers: getAuthHeaders() });
    const data = await response.json();
    return data.items;
}

async function fetchProducts() {
    const response = await fetch(`${API_BASE_URL}/products`, { headers: getAuthHeaders() });
    return await response.json();
}

async function loadProducts() {
    try {
        const response = await fetch(`${API_BASE_URL}/products`, { headers: getAuthHeaders() });
        const products = await response.json();
        const tbody = document.getElementById('products-table').querySelector('tbody');
        tbody.innerHTML = products.map(product => `
            <tr>
                <td>${product.product_name}</td>
                <td>${product.category || '-'}</td>
                <td>${product.model || '-'}</td>
                <td>${product.price ? `${product.currency} ${product.price}` : '-'}</td>
                <td>${product.min_order || '-'}</td>
                <td>
                    <button class="btn btn-edit" onclick="editProduct(${product.id})">编辑</button>
                    <button class="btn btn-delete" onclick="deleteProduct(${product.id})">删除</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load products error:', error);
    }
}

async function addProduct() {
    const formHtml = `
        <div class="form-group">
            <label>产品名称 *</label>
            <input type="text" name="product_name" required>
        </div>
        <div class="form-group">
            <label>类别</label>
            <input type="text" name="category">
        </div>
        <div class="form-group">
            <label>型号</label>
            <input type="text" name="model">
        </div>
        <div class="form-group">
            <label>价格</label>
            <input type="number" name="price" min="0" step="0.01">
        </div>
        <div class="form-group">
            <label>货币</label>
            <select name="currency">
                <option value="USD" selected>USD</option>
                <option value="CNY">CNY</option>
                <option value="EUR">EUR</option>
            </select>
        </div>
        <div class="form-group">
            <label>最小订单量</label>
            <input type="number" name="min_order" min="1">
        </div>
        <div class="form-group">
            <label>描述</label>
            <textarea name="description"></textarea>
        </div>
        <div class="form-group">
            <label>规格</label>
            <textarea name="specs"></textarea>
        </div>
    `;
    openModal('添加产品', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/products`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadProducts();
    });
}

async function editProduct(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/products/${id}`, { headers: getAuthHeaders() });
        const product = await response.json();
        const formHtml = `
            <input type="hidden" name="id" value="${product.id}">
            <div class="form-group">
                <label>产品名称 *</label>
                <input type="text" name="product_name" value="${product.product_name}" required>
            </div>
            <div class="form-group">
                <label>类别</label>
                <input type="text" name="category" value="${product.category || ''}">
            </div>
            <div class="form-group">
                <label>型号</label>
                <input type="text" name="model" value="${product.model || ''}">
            </div>
            <div class="form-group">
                <label>价格</label>
                <input type="number" name="price" min="0" step="0.01" value="${product.price || ''}">
            </div>
            <div class="form-group">
                <label>货币</label>
                <select name="currency">
                    <option value="USD" ${product.currency === 'USD' ? 'selected' : ''}>USD</option>
                    <option value="CNY" ${product.currency === 'CNY' ? 'selected' : ''}>CNY</option>
                    <option value="EUR" ${product.currency === 'EUR' ? 'selected' : ''}>EUR</option>
                </select>
            </div>
            <div class="form-group">
                <label>最小订单量</label>
                <input type="number" name="min_order" min="1" value="${product.min_order || ''}">
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea name="description">${product.description || ''}</textarea>
            </div>
            <div class="form-group">
                <label>规格</label>
                <textarea name="specs">${product.specs || ''}</textarea>
            </div>
        `;
        openModal('编辑产品', formHtml, async (data) => {
            const id = data.id;
            delete data.id;
            await fetch(`${API_BASE_URL}/products/${id}`, {
                method: 'PUT',
                headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            loadProducts();
        });
    } catch (error) {
        console.error('Edit product error:', error);
    }
}

async function deleteProduct(id) {
    if (confirm('确定要删除这个产品吗？')) {
        await fetch(`${API_BASE_URL}/products/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        loadProducts();
    }
}

async function loadEmails() {
    try {
        const customerId = document.getElementById('email-customer-filter').value;
        const url = customerId ? `${API_BASE_URL}/emails?customer_id=${customerId}` : `${API_BASE_URL}/emails`;
        const response = await fetch(url, { headers: getAuthHeaders() });
        const emails = await response.json();
        const tbody = document.getElementById('emails-table').querySelector('tbody');
        tbody.innerHTML = emails.map(email => `
            <tr>
                <td>${email.customer_id}</td>
                <td>${email.subject || '-'}</td>
                <td><span class="status-badge status-${email.status}">${email.status === 'sent' ? '已发送' : email.status}</span></td>
                <td>${email.sent_at ? new Date(email.sent_at).toLocaleString() : '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load emails error:', error);
    }
}

async function sendEmail() {
    const customers = await fetchCustomers();
    const formHtml = `
        <div class="form-group">
            <label>客户 *</label>
            <select name="customer_id" required>
                ${customers.map(c => `<option value="${c.id}">${c.company_name} - ${c.contact_person}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label>主题</label>
            <input type="text" name="subject">
        </div>
        <div class="form-group">
            <label>内容</label>
            <textarea name="content"></textarea>
        </div>
    `;
    openModal('发送邮件', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/emails`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadEmails();
    });
}

async function loadTasks() {
    try {
        const status = document.getElementById('task-status-filter').value;
        const url = status ? `${API_BASE_URL}/tasks?status=${status}` : `${API_BASE_URL}/tasks`;
        const response = await fetch(url, { headers: getAuthHeaders() });
        const tasks = await response.json();
        const tbody = document.getElementById('tasks-table').querySelector('tbody');
        tbody.innerHTML = tasks.map(task => `
            <tr>
                <td>${task.title}</td>
                <td>${task.description || '-'}</td>
                <td><span class="priority-${task.priority}">${getPriorityText(task.priority)}</span></td>
                <td><span class="status-badge status-${task.status}">${getStatusText(task.status)}</span></td>
                <td>${task.due_date ? new Date(task.due_date).toLocaleDateString() : '-'}</td>
                <td>${task.assignee || '-'}</td>
                <td>
                    <button class="btn btn-edit" onclick="editTask(${task.id})">编辑</button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load tasks error:', error);
    }
}

async function addTask() {
    const formHtml = `
        <div class="form-group">
            <label>标题 *</label>
            <input type="text" name="title" required>
        </div>
        <div class="form-group">
            <label>描述</label>
            <textarea name="description"></textarea>
        </div>
        <div class="form-group">
            <label>优先级</label>
            <select name="priority">
                <option value="high">高</option>
                <option value="normal" selected>中</option>
                <option value="low">低</option>
            </select>
        </div>
        <div class="form-group">
            <label>状态</label>
            <select name="status">
                <option value="pending" selected>待处理</option>
                <option value="in_progress">进行中</option>
                <option value="completed">已完成</option>
            </select>
        </div>
        <div class="form-group">
            <label>截止日期</label>
            <input type="date" name="due_date">
        </div>
        <div class="form-group">
            <label>负责人</label>
            <input type="text" name="assignee">
        </div>
    `;
    openModal('添加任务', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/tasks`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadTasks();
    });
}

async function editTask(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${id}`, { headers: getAuthHeaders() });
        const task = await response.json();
        const formHtml = `
            <input type="hidden" name="id" value="${task.id}">
            <div class="form-group">
                <label>状态</label>
                <select name="status">
                    <option value="pending" ${task.status === 'pending' ? 'selected' : ''}>待处理</option>
                    <option value="in_progress" ${task.status === 'in_progress' ? 'selected' : ''}>进行中</option>
                    <option value="completed" ${task.status === 'completed' ? 'selected' : ''}>已完成</option>
                </select>
            </div>
        `;
        openModal('编辑任务', formHtml, async (data) => {
            const id = data.id;
            delete data.id;
            await fetch(`${API_BASE_URL}/tasks/${id}`, {
                method: 'PUT',
                headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            loadTasks();
        });
    } catch (error) {
        console.error('Edit task error:', error);
    }
}

async function loadEvents() {
    try {
        const response = await fetch(`${API_BASE_URL}/events`, { headers: getAuthHeaders() });
        const events = await response.json();
        const tbody = document.getElementById('events-table').querySelector('tbody');
        tbody.innerHTML = events.map(event => `
            <tr>
                <td>${event.title}</td>
                <td>${event.description || '-'}</td>
                <td>${event.event_date ? new Date(event.event_date).toLocaleString() : '-'}</td>
                <td>${event.location || '-'}</td>
                <td>${event.type || '-'}</td>
                <td>${event.participants || '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Load events error:', error);
    }
}

async function addEvent() {
    const formHtml = `
        <div class="form-group">
            <label>活动名称 *</label>
            <input type="text" name="title" required>
        </div>
        <div class="form-group">
            <label>描述</label>
            <textarea name="description"></textarea>
        </div>
        <div class="form-group">
            <label>日期</label>
            <input type="datetime-local" name="event_date">
        </div>
        <div class="form-group">
            <label>地点</label>
            <input type="text" name="location">
        </div>
        <div class="form-group">
            <label>类型</label>
            <select name="type">
                <option value="exhibition">展会</option>
                <option value="meeting">会议</option>
                <option value="seminar">研讨会</option>
                <option value="other">其他</option>
            </select>
        </div>
        <div class="form-group">
            <label>预计人数</label>
            <input type="number" name="participants" min="1">
        </div>
    `;
    openModal('添加活动', formHtml, async (data) => {
        await fetch(`${API_BASE_URL}/events`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        loadEvents();
    });
}

function openModal(title, bodyHtml, onSubmit) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;
    document.getElementById('modal-overlay').classList.add('active');
    
    const form = document.getElementById('modal-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            if (value === '') return;
            if (!isNaN(value) && value !== '') {
                data[key] = parseFloat(value);
            } else {
                data[key] = value;
            }
        });
        await onSubmit(data);
        closeModal();
    };
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
    document.getElementById('modal-form').onsubmit = null;
}

async function loadDashboard() {
    try {
        const [customerAnalytics, inquiryAnalytics] = await Promise.all([
            fetch(`${API_BASE_URL}/analytics/customers`, { headers: getAuthHeaders() }).then(r => r.json()),
            fetch(`${API_BASE_URL}/analytics/inquiries`, { headers: getAuthHeaders() }).then(r => r.json())
        ]);
        
        document.getElementById('stat-customers').textContent = customerAnalytics.total;
        document.getElementById('stat-inquiries').textContent = inquiryAnalytics.total;
        document.getElementById('stat-pending').textContent = inquiryAnalytics.pending;
        document.getElementById('stat-rate').textContent = `${inquiryAnalytics.conversion_rate}%`;
        
        renderChart('customer-status-chart', customerAnalytics.by_status);
        renderChart('customer-country-chart', customerAnalytics.by_country);
    } catch (error) {
        console.error('Load dashboard error:', error);
    }
}

function renderChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!data || Object.keys(data).length === 0) {
        container.innerHTML = '<p style="text-align:center;color:#999;">暂无数据</p>';
        return;
    }
    
    const maxValue = Math.max(...Object.values(data));
    const bars = Object.entries(data).map(([label, value]) => {
        const height = maxValue > 0 ? (value / maxValue) * 150 : 0;
        return `
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div class="chart-bar" style="height:${height}px;"></div>
                <span class="chart-bar-label">${label}</span>
                <span class="chart-bar-value">${value}</span>
            </div>
        `;
    }).join('');
    
    container.innerHTML = `<div style="display:flex;justify-content:space-around;height:180px;align-items:flex-end;">${bars}</div>`;
}

function init() {
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const success = await login(email, password);
        if (success) {
            document.getElementById('login-screen').classList.remove('active');
            document.getElementById('main-screen').classList.add('active');
            document.getElementById('user-info').textContent = `欢迎, ${currentUser.username}`;
            loadDashboard();
        } else {
            document.getElementById('login-error').textContent = '邮箱或密码错误';
        }
    });

    document.getElementById('logout-btn').addEventListener('click', logout);

    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = link.dataset.view;
            showView(viewId);
            
            if (viewId === 'dashboard') loadDashboard();
            else if (viewId === 'customers') loadCustomers();
            else if (viewId === 'inquiries') loadInquiries();
            else if (viewId === 'products') loadProducts();
            else if (viewId === 'emails') loadEmails();
            else if (viewId === 'tasks') loadTasks();
            else if (viewId === 'events') loadEvents();
        });
    });

    document.getElementById('customer-search').addEventListener('input', loadCustomers);
    document.getElementById('customer-status-filter').addEventListener('change', loadCustomers);
    document.getElementById('inquiry-status-filter').addEventListener('change', loadInquiries);
    document.getElementById('email-customer-filter').addEventListener('input', loadEmails);
    document.getElementById('task-status-filter').addEventListener('change', loadTasks);

    document.getElementById('add-customer-btn').addEventListener('click', addCustomer);
    document.getElementById('add-inquiry-btn').addEventListener('click', addInquiry);
    document.getElementById('add-product-btn').addEventListener('click', addProduct);
    document.getElementById('send-email-btn').addEventListener('click', sendEmail);
    document.getElementById('add-task-btn').addEventListener('click', addTask);
    document.getElementById('add-event-btn').addEventListener('click', addEvent);

    document.getElementById('close-modal').addEventListener('click', closeModal);
    document.getElementById('cancel-modal').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('modal-overlay')) closeModal();
    });

    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (savedToken && savedUser) {
        currentToken = savedToken;
        currentUser = JSON.parse(savedUser);
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('main-screen').classList.add('active');
        document.getElementById('user-info').textContent = `欢迎, ${currentUser.username}`;
        loadDashboard();
    }
}

document.addEventListener('DOMContentLoaded', init);
