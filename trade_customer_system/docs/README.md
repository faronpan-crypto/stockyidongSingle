# 外贸获客系统

## 项目简介

外贸获客系统是一个专为外贸企业设计的客户管理和业务运营平台，帮助企业高效管理客户信息、询盘跟进、产品展示和业务数据分析。

## 技术栈

- **后端**: Flask + SQLAlchemy + SQLite
- **前端**: HTML5 + CSS3 + JavaScript (原生)
- **认证**: JWT (JSON Web Token)
- **跨域**: Flask-CORS

## 功能模块

### 1. 用户管理
- 用户注册与登录
- JWT Token认证
- 用户会话管理

### 2. 客户管理
- 客户信息录入与管理
- 客户状态追踪（潜在/已联系/洽谈中/已成交）
- 客户评分系统
- 客户搜索与筛选

### 3. 询盘管理
- 询盘录入与分配
- 询盘状态管理（待处理/已回复/洽谈中/已关闭）
- 优先级标记
- 询盘统计分析

### 4. 产品管理
- 产品信息管理
- 产品分类与规格
- 价格与最小订单量设置

### 5. 邮件营销
- 邮件发送记录
- 邮件内容管理

### 6. 任务管理
- 任务创建与分配
- 任务状态追踪
- 截止日期提醒

### 7. 展会活动
- 展会信息管理
- 活动日历

### 8. 数据仪表盘
- 客户统计分析
- 询盘转化率分析
- 可视化图表展示

## 项目结构

```
trade_customer_system/
├── backend/
│   ├── app.py              # Flask应用入口
│   ├── models.py           # SQLAlchemy模型定义
│   └── requirements.txt    # 后端依赖
├── frontend/
│   ├── index.html          # 主页面
│   ├── styles.css          # 样式文件
│   └── app.js              # 前端逻辑
├── config/
│   └── config.py           # 配置文件
├── data/
│   └── (数据库文件自动生成)
├── docs/
│   └── README.md           # 项目文档
└── .env                    # 环境变量配置
```

## 安装与运行

### 环境要求

- Python 3.8+
- pip 包管理器

### 安装步骤

1. **克隆项目**
```bash
cd /Users/faronpan/Agent/stockyidong_project/trade_customer_system
```

2. **安装依赖**
```bash
cd backend
pip install -r requirements.txt
```

3. **启动后端服务**
```bash
cd backend
python app.py
```

后端服务将在 `http://localhost:5000` 启动。

4. **启动前端**

使用浏览器打开 `frontend/index.html` 文件即可访问前端界面。

## API 接口说明

### 认证接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |

### 客户管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/customers` | GET | 获取客户列表 |
| `/api/customers/{id}` | GET | 获取客户详情 |
| `/api/customers` | POST | 创建客户 |
| `/api/customers/{id}` | PUT | 更新客户 |
| `/api/customers/{id}` | DELETE | 删除客户 |

### 询盘管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/inquiries` | GET | 获取询盘列表 |
| `/api/inquiries` | POST | 创建询盘 |
| `/api/inquiries/{id}` | PUT | 更新询盘 |

### 产品管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 获取产品列表 |
| `/api/products` | POST | 创建产品 |

### 邮件接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/emails` | GET | 获取邮件列表 |
| `/api/emails` | POST | 发送邮件 |

### 任务接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tasks` | GET | 获取任务列表 |
| `/api/tasks` | POST | 创建任务 |

### 活动接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/events` | GET | 获取活动列表 |
| `/api/events` | POST | 创建活动 |

### 数据分析接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/analytics/customers` | GET | 客户数据分析 |
| `/api/analytics/inquiries` | GET | 询盘数据分析 |

## 默认账户

系统启动时会自动创建一个管理员账户：

- **邮箱**: admin@example.com
- **密码**: admin123

## 使用说明

### 登录系统
1. 打开前端页面
2. 输入默认账户信息登录
3. 登录成功后进入仪表盘

### 管理客户
1. 点击左侧导航"客户管理"
2. 点击"添加客户"按钮
3. 填写客户信息并保存

### 处理询盘
1. 点击左侧导航"询盘管理"
2. 查看待处理询盘
3. 点击编辑按钮更新状态

### 查看数据
1. 点击左侧导航"仪表盘"
2. 查看业务概览统计
3. 查看客户分布图表

## 数据模型

### User (用户)
- id, username, email, password_hash, role, created_at, updated_at

### Customer (客户)
- id, company_name, contact_person, email, phone, country, city, industry, website, source, status, rating, notes, created_at, updated_at

### Product (产品)
- id, product_name, category, model, price, currency, min_order, description, specs, created_at, updated_at

### Inquiry (询盘)
- id, customer_id, product_id, subject, content, quantity, budget, currency, status, priority, source, reply_date, created_at, updated_at

### Email (邮件)
- id, customer_id, subject, content, status, sent_at, opened_at

### Task (任务)
- id, title, description, related_id, related_type, priority, status, due_date, assignee, created_at, updated_at

### Event (活动)
- id, title, description, event_date, location, type, participants, created_at

## 开发说明

### 添加新功能

1. 在 `models.py` 中定义数据模型
2. 在 `app.py` 中添加 API 路由
3. 在前端 `app.js` 中添加对应功能逻辑
4. 在 `index.html` 中添加页面元素

### 配置修改

- 修改 `.env` 文件配置数据库连接和 JWT 密钥
- 修改 `config/config.py` 配置应用参数

## 安全注意事项

1. 生产环境请修改 JWT_SECRET_KEY
2. 使用 HTTPS 协议传输数据
3. 定期备份数据库
4. 限制用户权限范围

## License

MIT License
