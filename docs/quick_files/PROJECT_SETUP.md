# Shop Hub - Complete Project Setup Guide

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Database Setup](#database-setup)
3. [Environment Configuration](#environment-configuration)
4. [Running the Project](#running-the-project)
5. [Creating Sample Data](#creating-sample-data)
6. [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### 1. Clone and Navigate
```bash
git clone <your-repo-url>
cd shop-hub
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 🗄️ Database Setup

### MySQL Installation

#### Windows:
1. Download MySQL Installer from [mysql.com](https://dev.mysql.com/downloads/installer/)
2. Run installer and choose "Developer Default"
3. Set root password during installation
4. Remember the port (default: 3306)

#### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install mysql-server
sudo mysql_secure_installation
```

#### macOS:
```bash
brew install mysql
brew services start mysql
mysql_secure_installation
```

### Create Database

```sql
-- Connect to MySQL
mysql -u root -p

-- Create database
CREATE DATABASE shophub_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user
CREATE USER 'shophub_user'@'localhost' IDENTIFIED BY 'YourSecurePassword123!';

-- Grant privileges
GRANT ALL PRIVILEGES ON shophub_db.* TO 'shophub_user'@'localhost';
FLUSH PRIVILEGES;

-- Verify
SHOW DATABASES;
EXIT;
```

## ⚙️ Environment Configuration

### 1. Copy Environment Template
```bash
cp env.example .env
```

### 2. Edit .env File

Open `.env` and configure:

```env
# Django Settings
SECRET_KEY=your-generated-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=shophub_db
DB_USER=shophub_user
DB_PASSWORD=YourSecurePassword123!
DB_HOST=localhost
DB_PORT=3306

# Gemini AI (Get from https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your-api-key-here
```

### 3. Generate Secret Key

Run in Python:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Or use:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 🏃 Running the Project

### 1. Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Create Superuser
```bash
python manage.py createsuperuser
```
Enter:
- Username: admin
- Email: admin@shophub.com
- Password: (secure password)

### 3. Create Static/Media Directories
```bash
# Windows PowerShell
New-Item -Path "media/products", "media/profiles", "media/vto" -ItemType Directory -Force

# Linux/Mac
mkdir -p media/{products,profiles,vto}
```

### 4. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 5. Run Development Server
```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

## 📦 Creating Sample Data

### Option 1: Django Admin
1. Go to http://127.0.0.1:8000/admin
2. Login with superuser credentials
3. Manually add:
   - Categories
   - Products
   - Users

### Option 2: Management Command (Create Later)
```bash
python manage.py load_sample_data
```

### Option 3: Django Shell
```bash
python manage.py shell
```

```python
from apps.accounts.models import User
from apps.products.models import Category, Product

# Create categories
electronics = Category.objects.create(
    name="Electronics",
    slug="electronics",
    description="Electronic devices and gadgets"
)

clothing = Category.objects.create(
    name="Clothing",
    slug="clothing",
    description="Fashion and apparel"
)

# Create a seller
seller = User.objects.create_user(
    username='testseller',
    email='seller@test.com',
    password='password123',
    role='seller',
    full_name='Test Seller'
)

# Create products
Product.objects.create(
    seller=seller,
    category=electronics,
    name="Wireless Headphones",
    description="High-quality bluetooth headphones",
    price=99.99,
    compare_at_price=149.99,
    inventory=50,
    status='active'
)
```

## 🛠️ Troubleshooting

### MySQL Connection Error
```
django.db.utils.OperationalError: (2002, "Can't connect to MySQL server")
```
**Solution:**
- Check if MySQL is running: `systemctl status mysql` (Linux) or check Task Manager (Windows)
- Verify credentials in `.env` file
- Test connection: `mysql -u shophub_user -p`

### Module Not Found Error
```
ModuleNotFoundError: No module named 'mysqlclient'
```
**Solution:**
```bash
pip install mysqlclient
# If fails on Windows, install: pip install mysqlclient-wheel
```

### Migration Error
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```
**Solution:**
```bash
# Drop all tables (CAUTION: Deletes all data)
python manage.py flush
python manage.py migrate
```

### Static Files Not Loading
**Solution:**
```bash
python manage.py collectstatic --clear --noinput
```

### Port Already in Use
```
Error: That port is already in use.
```
**Solution:**
```bash
# Use different port
python manage.py runserver 8001

# Or kill the process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <process_id> /F

# Linux/Mac:
lsof -i :8000
kill -9 <process_id>
```

## 📱 Testing the Setup

### 1. Check Database Connection
```bash
python manage.py dbshell
```

### 2. Run Tests
```bash
python manage.py test
```

### 3. Check for Issues
```bash
python manage.py check
```

## 🔐 Security Checklist

Before deploying:
- [ ] Change DEBUG to False
- [ ] Set strong SECRET_KEY
- [ ] Configure ALLOWED_HOSTS
- [ ] Use environment variables for sensitive data
- [ ] Enable HTTPS
- [ ] Set up proper database credentials
- [ ] Configure CORS properly
- [ ] Enable security middleware

## 📚 Next Steps

1. Follow the TODO list in `TODO.md`
2. Read API documentation in `docs/API.md`
3. Check deployment guide in `docs/DEPLOYMENT.md`
4. Review contributing guidelines in `CONTRIBUTING.md`

## 💬 Getting Help

- Check existing issues on GitHub
- Read Django documentation: https://docs.djangoproject.com/
- Join our community discussions
- Contact: support@shophub.com

