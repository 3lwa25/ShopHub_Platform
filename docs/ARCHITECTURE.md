# Shop Hub - System Architecture

## 🏗️ Overall Architecture

Shop Hub follows a **Model-View-Template (MVT)** architecture pattern using Django framework, with additional REST API endpoints for modern frontend integration.

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web UI     │  │  Mobile App  │  │  Third-Party │      │
│  │  (Templates) │  │   (API)      │  │  Integrations│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │  Django Templates  │  │   REST API (DRF)   │            │
│  │    (Views/URLs)    │  │   (Serializers)    │            │
│  └────────┬───────────┘  └────────┬───────────┘            │
└───────────┼──────────────────────┼─────────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC LAYER                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Accounts │  │ Products │  │  Orders  │  │   Cart   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Rewards │  │   VTO    │  │ Chatbot  │  │  Seller  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                       DATA ACCESS LAYER                      │
│                    (Django ORM / Models)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATABASE LAYER                          │
│                      MySQL 8.0                               │
└─────────────────────────────────────────────────────────────┘

                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Gemini  │    │  Media  │    │  Redis  │
    │   AI    │    │ Storage │    │  Cache  │
    └─────────┘    └─────────┘    └─────────┘
  EXTERNAL SERVICES
```

## 📦 Application Structure

### Core Apps

#### 1. **accounts** - User Management
```
accounts/
├── models.py        # User, Profile, Seller Profile
├── views.py         # Registration, Login, Profile
├── forms.py         # User forms
├── admin.py         # Admin interface
├── urls.py          # URL routing
└── api_urls.py      # REST API endpoints
```

**Responsibilities:**
- User authentication (login/signup/logout)
- User profiles (buyer/seller)
- Role-based access control
- Profile management

#### 2. **products** - Product Catalog
```
products/
├── models.py        # Product, Category, Review, ProductImage
├── views.py         # Product listing, detail, search
├── admin.py         # Product administration
├── filters.py       # Search and filter logic
├── urls.py          # Product URLs
└── api_urls.py      # Product REST API
```

**Responsibilities:**
- Product CRUD operations
- Category management
- Product search and filtering
- Reviews and ratings
- Product images

#### 3. **cart** - Shopping Cart
```
cart/
├── models.py        # Cart, CartItem
├── views.py         # Add/remove items, view cart
├── context_processors.py  # Cart in all templates
├── urls.py          # Cart URLs
└── api_urls.py      # Cart REST API
```

**Responsibilities:**
- Add products to cart
- Update quantities
- Remove items
- Calculate totals
- Persist cart (logged-in users)

#### 4. **orders** - Order Management
```
orders/
├── models.py        # Order, OrderItem, OrderStatus
├── views.py         # Checkout, order history
├── forms.py         # Checkout form
├── urls.py          # Order URLs
└── api_urls.py      # Order REST API
```

**Responsibilities:**
- Checkout process
- Order creation
- Order tracking
- Order history
- Order status updates

#### 5. **rewards** - Loyalty Program
```
rewards/
├── models.py        # PointsAccount, Transaction, Reward
├── views.py         # Points balance, redeem
├── utils.py         # Points calculation
├── urls.py          # Rewards URLs
└── api_urls.py      # Rewards REST API
```

**Responsibilities:**
- Points accumulation
- Points redemption
- Referral bonuses
- Loyalty rewards

#### 6. **ai_chatbot** - Gemini AI Integration
```
ai_chatbot/
├── models.py        # ChatHistory, Message
├── views.py         # Chat interface
├── gemini_service.py  # Gemini API wrapper
├── urls.py          # Chat URLs
└── api_urls.py      # Chat REST API
```

**Responsibilities:**
- AI-powered chatbot
- Product recommendations
- Natural language queries
- Chat history

#### 7. **virtual_tryon** - Virtual Try-On
```
virtual_tryon/
├── models.py        # TryOnSession, TryOnImage
├── views.py         # Upload, process, view
├── ai_processor.py  # Image processing logic
├── urls.py          # VTO URLs
└── api_urls.py      # VTO REST API
```

**Responsibilities:**
- Image upload
- AI-powered product overlay
- Image enhancement
- Try-on history

#### 8. **seller** - Seller Dashboard
```
seller/
├── models.py        # SellerAnalytics, SellerSettings
├── views.py         # Dashboard, product management
├── forms.py         # Product forms
├── urls.py          # Seller URLs
└── decorators.py    # Seller-only access
```

**Responsibilities:**
- Seller dashboard
- Product management
- Sales analytics
- Inventory tracking
- Order fulfillment

#### 9. **reviews** - Product Reviews
```
reviews/
├── models.py        # Review, ReviewImage, ReviewVote
├── views.py         # Add/edit reviews
├── forms.py         # Review form
└── urls.py          # Review URLs
```

#### 10. **wishlist** - Wishlist Feature
```
wishlist/
├── models.py        # Wishlist, WishlistItem
├── views.py         # Add/remove items
└── urls.py          # Wishlist URLs
```

## 🗄️ Database Design

### Entity Relationship Diagram

```
┌──────────────┐         ┌──────────────┐
│     User     │◄────────┤   Profile    │
└──────┬───────┘         └──────────────┘
       │
       │ 1:N
       │
       ▼
┌──────────────┐         ┌──────────────┐
│  Product     │◄────────┤   Category   │
└──────┬───────┘         └──────────────┘
       │
       │ 1:N
       │
       ├──────────┐
       ▼          ▼
┌──────────┐  ┌──────────┐
│CartItem  │  │OrderItem │
└──────────┘  └──────────┘
       │          │
       ▼          ▼
┌──────────┐  ┌──────────┐
│   Cart   │  │  Order   │
└──────────┘  └──────────┘
```

### Key Models

#### User Model
```python
- id (UUID)
- username (unique)
- email (unique)
- password (hashed)
- role (buyer/seller)
- full_name
- avatar
- is_active
- date_joined
```

#### Product Model
```python
- id (UUID)
- seller (FK: User)
- category (FK: Category)
- name
- description
- price
- compare_at_price
- inventory
- images (JSONField)
- specifications (JSONField)
- status (active/draft/archived)
- created_at
- updated_at
```

#### Order Model
```python
- id (UUID)
- buyer (FK: User)
- order_number (unique)
- total_amount
- status (pending/confirmed/shipped/delivered)
- shipping_address (JSONField)
- payment_method
- created_at
- updated_at
```

## 🔄 Request Flow

### 1. User Views Product
```
Browser → URL Router → Product View → Product Model → Template → HTML
```

### 2. Add to Cart (API)
```
Frontend → API Endpoint → CartView → Cart Model → JSON Response
```

### 3. AI Chatbot Query
```
User Input → Chatbot API → Gemini Service → Product Query → AI Response
```

### 4. Virtual Try-On
```
Image Upload → VTO Processor → AI Enhancement → Overlay → Return Image
```

## 🔒 Security Architecture

### Authentication
- Session-based authentication for web UI
- JWT tokens for REST API
- Password hashing with PBKDF2
- CSRF protection

### Authorization
- Role-based access control (RBAC)
- Permission decorators (@login_required, @seller_required)
- Row-level permissions
- Django permissions framework

### Data Protection
- HTTPS/TLS encryption
- SQL injection prevention (ORM)
- XSS prevention (template escaping)
- CORS configuration

## 🚀 Performance Optimization

### Caching Strategy
```python
# View caching
@cache_page(60 * 15)  # 15 minutes
def product_list(request):
    ...

# Query optimization
products = Product.objects.select_related('category')\
                         .prefetch_related('images')\
                         .filter(status='active')
```

### Database Optimization
- Indexed fields (email, username, product name)
- Query optimization with select_related/prefetch_related
- Database connection pooling
- Pagination for large datasets

### Static File Handling
- WhiteNoise for static file serving
- CDN integration (optional)
- Image optimization
- Lazy loading

## 📡 API Design

### RESTful Endpoints

```
Products:
GET    /api/products/              # List products
GET    /api/products/{id}/         # Product detail
POST   /api/products/              # Create (seller only)
PUT    /api/products/{id}/         # Update (seller only)
DELETE /api/products/{id}/         # Delete (seller only)

Cart:
GET    /api/cart/                  # View cart
POST   /api/cart/add/              # Add item
PUT    /api/cart/{id}/             # Update quantity
DELETE /api/cart/{id}/             # Remove item

Orders:
POST   /api/orders/                # Create order
GET    /api/orders/                # List orders
GET    /api/orders/{id}/           # Order detail

Chatbot:
POST   /api/chatbot/chat/          # Send message
GET    /api/chatbot/history/       # Chat history

Virtual Try-On:
POST   /api/vto/process/           # Process image
GET    /api/vto/history/           # Try-on history
```

## 🔌 External Integrations

### Google Gemini AI
```python
from google.generativeai import GenerativeModel

model = GenerativeModel('gemini-pro')
response = model.generate_content(prompt)
```

### Payment Gateway (Future)
- Stripe/PayPal integration
- Webhook handling
- Transaction management

### Email Service
- SMTP configuration
- Order confirmations
- Password resets
- Marketing emails

## 📈 Scalability Considerations

### Horizontal Scaling
- Stateless application design
- Load balancer ready
- Session storage in Redis
- Media files on S3/CDN

### Vertical Scaling
- Database optimization
- Query caching
- Background task processing (Celery)
- Connection pooling

## 🧪 Testing Strategy

### Unit Tests
- Model tests
- View tests
- Form validation tests
- Utility function tests

### Integration Tests
- API endpoint tests
- User flow tests
- Payment processing tests

### End-to-End Tests
- Selenium/Cypress tests
- User journey testing

## 📊 Monitoring & Logging

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info('User logged in')
logger.error('Payment failed', exc_info=True)
```

### Monitoring
- Error tracking (Sentry)
- Performance monitoring
- User analytics
- Database query analysis

---

**Last Updated:** November 2025  
**Version:** 1.0.0

