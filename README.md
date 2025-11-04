# 🛍️ Shop Hub - AI-Powered Online Shopping Platform

<div align="center">

![Shop Hub](https://img.shields.io/badge/Shop%20Hub-AI%20Shopping-blueviolet?style=for-the-badge)
![Django](https://img.shields.io/badge/Django-5.0-green?style=for-the-badge&logo=django)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange?style=for-the-badge&logo=mysql)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**An intelligent e-commerce platform combining the power of AI with seamless shopping experience**

[Features](#-features) • [Tech Stack](#-tech-stack) • [Installation](#-installation) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [AI Features](#-ai-features)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

---

## 🌟 Overview

**Shop Hub** is a next-generation e-commerce platform inspired by Amazon, enhanced with cutting-edge AI features to solve common online shopping challenges. Built with Django and powered by Google's Gemini AI, Shop Hub provides an intelligent, trustworthy, and user-friendly shopping experience.

### 🎯 Problem Statement

Modern e-commerce platforms face several critical challenges:
- **Trust Issues**: Customers can't verify product quality before purchase
- **Poor UX**: Page reloads disrupt browsing experience
- **Decision Paralysis**: Difficulty choosing between similar products
- **Visualization Gap**: Can't see how products look in real life

### 💡 Our Solution

Shop Hub addresses these challenges through:
- **AI Virtual Try-On**: Preview products on your photos with realistic AI enhancement
- **Smart Filtering**: Intelligent product recommendations based on preferences
- **AI Chatbot**: Real-time shopping assistance using Gemini API
- **Reward Points System**: Loyalty program to encourage repeat purchases
- **Seamless Navigation**: Smooth scrolling without page reloads
- **Secure Payments**: Payment simulation with professional checkout flow

---

## ✨ Features

### 🛒 For Buyers

- **🔍 Smart Product Discovery**
  - Advanced search with AI-powered suggestions
  - Category-based filtering
  - Price range and specification filters
  - Sort by popularity, price, ratings

- **🤖 AI Shopping Assistant**
  - Natural language product queries
  - Product comparison and recommendations
  - Personalized shopping advice
  - 24/7 availability via Gemini AI

- **👗 Virtual Try-On (VTO)**
  - Upload your photo
  - AI-enhanced product overlay
  - Realistic rendering
  - Works with clothing, accessories, and more

- **🛍️ Shopping Experience**
  - Intuitive shopping cart
  - Wishlist functionality
  - Order tracking
  - Order history with detailed views

- **🎁 Rewards Program**
  - Earn points on every purchase
  - Redeem points for discounts
  - Special loyalty benefits
  - Referral bonuses

### 🏪 For Sellers

- **📊 Seller Dashboard**
  - Sales analytics and insights
  - Inventory management
  - Order fulfillment tracking
  - Revenue reports

- **📦 Product Management**
  - Easy product listing
  - Multiple image upload
  - Variant management (size, color, etc.)
  - Bulk operations

- **💼 Business Tools**
  - Customer analytics
  - Marketing tools
  - Promotional campaigns
  - Performance metrics

### 🔐 Security & Trust

- **User Authentication**: Secure login/signup with email verification
- **Role-Based Access**: Buyer, Seller, and Admin roles
- **Data Protection**: Encrypted data storage
- **Secure Checkout**: PCI-compliant payment simulation
- **Review System**: Verified purchase reviews

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Django 5.0
- **Language**: Python 3.11+
- **Database**: MySQL 8.0
- **ORM**: Django ORM
- **API**: Django REST Framework (DRF)
- **Authentication**: Django Auth + JWT

### Frontend
- **Core**: HTML5, CSS3, JavaScript (ES6+)
- **Styling**: Bootstrap 5 + Custom CSS
- **Icons**: Font Awesome
- **Charts**: Chart.js (for analytics)

### AI & Machine Learning
- **AI Engine**: Google Gemini API
- **Image Processing**: Pillow (PIL)
- **VTO**: Custom AI overlay system
- **Recommendations**: Collaborative filtering

### DevOps & Tools
- **Version Control**: Git & GitHub
- **Environment**: Python venv
- **Task Queue**: Celery (optional)
- **Caching**: Redis (optional)
- **Server**: Gunicorn + Nginx (production)

---

## 📁 Project Structure

```
shop-hub/
├── shophub/                    # Main Django project
│   ├── __init__.py
│   ├── settings.py            # Project settings
│   ├── urls.py                # Main URL configuration
│   ├── wsgi.py                # WSGI config
│   └── asgi.py                # ASGI config
│
├── apps/                      # Django applications
│   ├── accounts/              # User authentication & profiles
│   │   ├── models.py         # User, Profile models
│   │   ├── views.py          # Auth views
│   │   ├── forms.py          # Registration/login forms
│   │   └── urls.py           # Auth URLs
│   │
│   ├── products/              # Product catalog
│   │   ├── models.py         # Product, Category, Review
│   │   ├── views.py          # Product views
│   │   ├── admin.py          # Admin configuration
│   │   └── urls.py           # Product URLs
│   │
│   ├── cart/                  # Shopping cart
│   │   ├── models.py         # Cart, CartItem
│   │   ├── views.py          # Cart operations
│   │   ├── context_processors.py  # Cart context
│   │   └── urls.py           # Cart URLs
│   │
│   ├── orders/                # Order management
│   │   ├── models.py         # Order, OrderItem
│   │   ├── views.py          # Checkout, order views
│   │   ├── forms.py          # Checkout form
│   │   └── urls.py           # Order URLs
│   │
│   ├── rewards/               # Loyalty program
│   │   ├── models.py         # Points, Rewards
│   │   ├── views.py          # Rewards views
│   │   └── urls.py           # Rewards URLs
│   │
│   ├── ai_chatbot/            # Gemini AI integration
│   │   ├── views.py          # Chat API
│   │   ├── gemini_service.py # Gemini client
│   │   └── urls.py           # Chat URLs
│   │
│   ├── virtual_tryon/         # VTO feature
│   │   ├── models.py         # TryOn sessions
│   │   ├── views.py          # VTO processing
│   │   ├── ai_processor.py   # AI overlay logic
│   │   └── urls.py           # VTO URLs
│   │
│   └── seller/                # Seller dashboard
│       ├── models.py         # Seller profile
│       ├── views.py          # Dashboard views
│       ├── forms.py          # Product forms
│       └── urls.py           # Seller URLs
│
├── templates/                 # HTML templates
│   ├── base.html             # Base template
│   ├── home.html             # Landing page
│   ├── accounts/             # Auth templates
│   ├── products/             # Product templates
│   ├── cart/                 # Cart templates
│   ├── orders/               # Order templates
│   ├── chatbot/              # AI chat interface
│   ├── vto/                  # Virtual try-on UI
│   └── seller/               # Seller dashboard
│
├── static/                    # Static files
│   ├── css/                  # Stylesheets
│   │   ├── main.css
│   │   ├── products.css
│   │   └── chatbot.css
│   ├── js/                   # JavaScript
│   │   ├── main.js
│   │   ├── cart.js
│   │   ├── chatbot.js
│   │   └── vto.js
│   └── images/               # Static images
│
├── media/                     # User uploads
│   ├── products/             # Product images
│   ├── profiles/             # Profile pictures
│   └── vto/                  # Try-on photos
│
├── docs/                      # Documentation
│   ├── API.md                # API documentation
│   ├── DEPLOYMENT.md         # Deployment guide
│   └── CONTRIBUTING.md       # Contribution guidelines
│
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── manage.py                 # Django management
├── README.md                 # This file
└── LICENSE                   # MIT License
```

---

## 🚀 Installation

### Prerequisites

Ensure you have the following installed:
- **Python**: 3.11 or higher
- **MySQL**: 8.0 or higher
- **Git**: Latest version
- **pip**: Python package manager

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/shop-hub.git
cd shop-hub
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up MySQL Database

```sql
CREATE DATABASE shophub_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'shophub_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON shophub_db.* TO 'shophub_user'@'localhost';
FLUSH PRIVILEGES;
```

### Step 5: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` file:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=shophub_db
DB_USER=shophub_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=3306

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key

# Email (Optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password
```

### Step 6: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 7: Create Superuser

```bash
python manage.py createsuperuser
```

### Step 8: Load Sample Data (Optional)

```bash
python manage.py loaddata sample_data.json
```

### Step 9: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Step 10: Run Development Server

```bash
python manage.py runserver
```

Visit: `http://127.0.0.1:8000/`

---

## ⚙️ Configuration

### Gemini API Setup

1. Get API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Add to `.env` file:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

### Email Configuration

For email notifications (order confirmations, etc.):

```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
```

---

## 📖 Usage

### For Buyers

1. **Register**: Create account as a buyer
2. **Browse**: Explore products by category
3. **AI Chat**: Ask the AI assistant for recommendations
4. **Virtual Try-On**: Upload photo to try products virtually
5. **Add to Cart**: Select desired products
6. **Checkout**: Complete purchase
7. **Earn Points**: Get reward points on each order

### For Sellers

1. **Register**: Sign up as a seller
2. **Dashboard**: Access seller dashboard
3. **Add Products**: List products with images and details
4. **Manage Inventory**: Track stock levels
5. **View Orders**: Process customer orders
6. **Analytics**: Monitor sales performance

---

## 🤖 AI Features

### 1. AI Chatbot (Gemini)

**Capabilities**:
- Natural language product search
- Product comparisons
- Personalized recommendations
- Shopping assistance
- FAQ handling

**Usage**:
```javascript
// Frontend API call
fetch('/api/chatbot/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Show me wireless headphones under $100'
  })
})
```

### 2. Virtual Try-On

**Features**:
- AI-powered image overlay
- Realistic product rendering
- Multiple product types support
- Photo enhancement

**How it works**:
1. User uploads photo
2. Selects product to try
3. AI processes and overlays product
4. Enhanced image returned

### 3. Smart Recommendations

**Algorithms**:
- Collaborative filtering
- Content-based filtering
- User behavior tracking
- Purchase history analysis

---

## 📚 API Documentation

### Authentication

```http
POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/logout/
GET  /api/auth/profile/
```

### Products

```http
GET    /api/products/              # List all products
GET    /api/products/:id/          # Product detail
POST   /api/products/              # Create product (seller)
PUT    /api/products/:id/          # Update product (seller)
DELETE /api/products/:id/          # Delete product (seller)
GET    /api/products/search/       # Search products
```

### Cart

```http
GET    /api/cart/                  # View cart
POST   /api/cart/add/              # Add to cart
PUT    /api/cart/update/:id/       # Update quantity
DELETE /api/cart/remove/:id/       # Remove item
```

### Orders

```http
GET    /api/orders/                # List orders
POST   /api/orders/create/         # Place order
GET    /api/orders/:id/            # Order detail
```

### AI Chatbot

```http
POST   /api/chatbot/               # Send message
GET    /api/chatbot/history/       # Chat history
```

### Virtual Try-On

```http
POST   /api/vto/process/           # Process try-on
GET    /api/vto/history/           # Try-on history
```

For detailed API documentation, see [API.md](docs/API.md)

---

## 🧪 Testing

Run tests:

```bash
# All tests
python manage.py test

# Specific app
python manage.py test apps.products

# With coverage
coverage run --source='.' manage.py test
coverage report
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use strong `SECRET_KEY`
- [ ] Set up MySQL in production
- [ ] Configure static files with Nginx
- [ ] Set up SSL certificate (HTTPS)
- [ ] Configure email backend
- [ ] Set up error logging
- [ ] Enable security middleware
- [ ] Configure CORS properly

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed guide.

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Contact

**Project Maintainer**: Your Name
- GitHub: [@3lwa25](https://github.com/3lwa25)
- Email: Mohamedalimohamed210@gmail.com

**Project Link**: [https://github.com/3lwa25/Github_OnlineShopping-Repo.git](https://github.com/3lwa25/Github_OnlineShopping-Repo.git)

---

## 🙏 Acknowledgments

- **Google Gemini AI** for powering intelligent features
- **Django Community** for the amazing framework
- **Bootstrap** for responsive UI components
- Inspired by platforms like Amazon, Noon, Jumia, and Shein

---

## 📊 Project Status

![GitHub Issues](https://img.shields.io/github/issues/3lwa25/Github_OnlineShopping-Repo.git)
![GitHub Pull Requests](https://img.shields.io/github/issues-pr/3lwa25/Github_OnlineShopping-Repo.git)
![GitHub Stars](https://img.shields.io/github/stars/3lwa25/Github_OnlineShopping-Repo.git)
![GitHub Forks](https://img.shields.io/github/forks/3lwa25/Github_OnlineShopping-Repo.git)

---

<div align="center">

**Made with ❤️ by the Shop Hub Team**

⭐ Star us on GitHub if you find this project useful!

</div>

