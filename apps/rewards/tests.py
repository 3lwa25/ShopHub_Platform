from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.rewards.models import RewardAccount


class RewardsViewsTests(TestCase):
    """Basic smoke tests to ensure rewards pages render correctly."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="tester@example.com",
            password="testpass123",
            username="tester",
        )
        self.reward_account = RewardAccount.objects.create(
            user=self.user,
            points_balance=1000,
            total_earned=1000,
            total_spent=0,
            tier="bronze",
        )
        self.client.force_login(self.user)

    def test_transaction_history_page_renders(self):
        """Ensure rewards history page loads without errors."""
        url = reverse("rewards:history")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transaction History")

    def test_earn_points_page_renders(self):
        """Ensure earn points info page loads without errors."""
        url = reverse("rewards:earn_info")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How to Earn Points")

