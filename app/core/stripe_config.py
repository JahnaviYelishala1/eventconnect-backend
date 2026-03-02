import stripe
from app.core.config import settings

# Configure global Stripe SDK API key from environment-backed settings.
stripe.api_key = settings.stripe_secret_key
