"""
Comprehensive Test Suite for Shop Hub
Tests all major functionality across the platform
"""
import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import datetime, timedelta

from apps.products.models import Product, Category, ProductImage
from apps.orders.models import Order, OrderItem
from apps.cart.models import Cart, CartItem
from apps.reviews.models import Review
from apps.wishlist.models import Wishlist, WishlistItem
from apps.rewards.models import RewardAccount, PointsTransaction, Reward
from apps.ai_chatbot.models import ChatSession, ChatMessage
from apps.virtual_tryon.models import VTOSession

User = get_user_model()


class UserAuthenticationTests(TestCase):
    """Test user authentication and registration"""
    
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'email': 'testuser@example.com',
            'username': 'testuser',
            'password': 'testpass123',
            'full_name': 'Test User'
        }
    
    def test_user_registration(self):
        """Test user can register"""
        response = self.client.post(reverse('accounts:register'), self.user_data)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.email, self.user_data['email'])
    
    def test_user_login(self):
        """Test user can login"""
        user = User.objects.create_user(**self.user_data)
        response = self.client.post(reverse('accounts:login'), {
            'username': self.user_data['email'],
            'password': self.user_data['password']
        })
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_user_logout(self):
        """Test user can logout"""
        user = User.objects.create_user(**self.user_data)
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:logout'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class ProductCatalogTests(TestCase):
    """Test product catalog functionality"""
    
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics',
            is_active=True
        )
        self.seller = User.objects.create_user(
            email='seller@example.com',
            username='seller',
            password='sellerpass',
            role='seller'
        )
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Product',
            slug='test-product',
            description='Test description',
            price=Decimal('99.99'),
            stock=100,
            status='active'
        )
    
    def test_product_list_view(self):
        """Test product listing page"""
        response = self.client.get(reverse('products:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
    
    def test_product_detail_view(self):
        """Test product detail page"""
        response = self.client.get(reverse('products:product_detail', args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
    
    def test_category_view(self):
        """Test category page"""
        response = self.client.get(reverse('products:category_products', args=[self.category.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
    
    def test_product_search(self):
        """Test product search"""
        response = self.client.get(reverse('products:product_list'), {'q': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)


class ShoppingCartTests(TestCase):
    """Test shopping cart functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='buyer@example.com',
            username='buyer',
            password='buyerpass',
            role='buyer'
        )
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.product = Product.objects.create(
            seller=User.objects.create_user(email='s@example.com', username='s', password='p', role='seller'),
            category=self.category,
            title='Test Product',
            slug='test-product',
            price=Decimal('50.00'),
            stock=10,
            status='active'
        )
        self.client.force_login(self.user)
    
    def test_add_to_cart(self):
        """Test adding product to cart"""
        response = self.client.post(reverse('cart:add_to_cart'), {
            'product_id': self.product.id,
            'quantity': 2
        })
        self.assertEqual(response.status_code, 200)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().quantity, 2)
    
    def test_remove_from_cart(self):
        """Test removing product from cart"""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        response = self.client.post(reverse('cart:remove_from_cart', args=[cart_item.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(cart.items.count(), 0)
    
    def test_update_cart_quantity(self):
        """Test updating cart item quantity"""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        response = self.client.post(reverse('cart:update_cart', args=[cart_item.id]), {
            'quantity': 3
        })
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 3)


class OrderManagementTests(TestCase):
    """Test order management"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='buyer@example.com',
            username='buyer',
            password='buyerpass'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            seller=User.objects.create_user(email='s@example.com', username='s', password='p', role='seller'),
            category=self.category,
            title='Test Product',
            slug='test-product',
            price=Decimal('100.00'),
            stock=10,
            status='active'
        )
        self.client.force_login(self.user)
    
    def test_create_order(self):
        """Test order creation"""
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        
        response = self.client.post(reverse('orders:checkout'), {
            'shipping_address': '123 Test St',
            'payment_method': 'credit_card'
        })
        
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.buyer, self.user)
        self.assertEqual(order.items.count(), 1)
    
    def test_order_list_view(self):
        """Test order list page"""
        order = Order.objects.create(
            buyer=self.user,
            total_amount=Decimal('200.00'),
            status='pending'
        )
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)


class ReviewSystemTests(TestCase):
    """Test review system"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            seller=User.objects.create_user(email='s@example.com', username='s', password='p', role='seller'),
            category=self.category,
            title='Test Product',
            slug='test-product',
            price=Decimal('50.00'),
            stock=10,
            status='active'
        )
        self.client.force_login(self.user)
    
    def test_create_review(self):
        """Test creating a review"""
        response = self.client.post(reverse('reviews:write_review', args=[self.product.slug]), {
            'rating': 5,
            'title': 'Great product',
            'comment': 'Really satisfied with this purchase'
        })
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.user, self.user)


class WishlistTests(TestCase):
    """Test wishlist functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            seller=User.objects.create_user(email='s@example.com', username='s', password='p', role='seller'),
            category=self.category,
            title='Test Product',
            slug='test-product',
            price=Decimal('50.00'),
            stock=10,
            status='active'
        )
        self.client.force_login(self.user)
    
    def test_add_to_wishlist(self):
        """Test adding product to wishlist"""
        response = self.client.post(reverse('wishlist:toggle', args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        wishlist = Wishlist.objects.get(user=self.user)
        self.assertEqual(wishlist.items.count(), 1)
    
    def test_remove_from_wishlist(self):
        """Test removing product from wishlist"""
        wishlist = Wishlist.objects.create(user=self.user)
        WishlistItem.objects.create(wishlist=wishlist, product=self.product)
        response = self.client.post(reverse('wishlist:toggle', args=[self.product.id]))
        self.assertEqual(wishlist.items.count(), 0)


class RewardsSystemTests(TestCase):
    """Test rewards system"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass'
        )
        self.reward_account = RewardAccount.objects.create(
            user=self.user,
            points_balance=1000
        )
        self.client.force_login(self.user)
    
    def test_rewards_dashboard(self):
        """Test rewards dashboard loads"""
        response = self.client.get(reverse('rewards:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1000')  # Points balance
    
    def test_add_points(self):
        """Test adding points"""
        self.reward_account.add_points(500, 'purchase', 'Test purchase')
        self.reward_account.refresh_from_db()
        self.assertEqual(self.reward_account.points_balance, 1500)
    
    def test_redeem_points(self):
        """Test redeeming points"""
        self.reward_account.redeem_points(200, 'redeemed', 'Test redemption')
        self.reward_account.refresh_from_db()
        self.assertEqual(self.reward_account.points_balance, 800)


class AIChatbotTests(TestCase):
    """Test AI chatbot functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass'
        )
        self.client.force_login(self.user)
    
    def test_chat_home(self):
        """Test chat home page loads"""
        response = self.client.get(reverse('ai_chatbot:chat_home'))
        self.assertEqual(response.status_code, 200)
    
    def test_create_session(self):
        """Test creating chat session"""
        session = ChatSession.objects.create(user=self.user)
        self.assertEqual(ChatSession.objects.count(), 1)


class VirtualTryOnTests(TestCase):
    """Test Virtual Try-On functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass'
        )
        self.client.force_login(self.user)
    
    def test_vto_home(self):
        """Test VTO home page loads"""
        response = self.client.get(reverse('virtual_tryon:home'))
        self.assertEqual(response.status_code, 200)


class IntegrationTests(TestCase):
    """Integration tests for complete user flows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@example.com',
            username='user',
            password='pass',
            role='buyer'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            seller=User.objects.create_user(email='s@example.com', username='s', password='p', role='seller'),
            category=self.category,
            title='Test Product',
            slug='test-product',
            price=Decimal('100.00'),
            stock=10,
            status='active'
        )
    
    def test_complete_purchase_flow(self):
        """Test complete purchase flow from browsing to order"""
        # 1. View product
        response = self.client.get(reverse('products:product_detail', args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        
        # 2. Login
        self.client.force_login(self.user)
        
        # 3. Add to cart
        response = self.client.post(reverse('cart:add_to_cart'), {
            'product_id': self.product.id,
            'quantity': 1
        })
        self.assertEqual(response.status_code, 200)
        
        # 4. View cart
        response = self.client.get(reverse('cart:view_cart'))
        self.assertEqual(response.status_code, 200)
        
        # 5. Checkout (simplified)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)


# Run tests with: python manage.py test tests.test_comprehensive

