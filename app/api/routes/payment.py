from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.stripe_config import stripe
from app.database import SessionLocal
from app.models.event_booking import EventBooking
from app.models.payment import Payment

router = APIRouter(prefix="/api/payments", tags=["Payments"])


# ==========================================================
# ✅ Create Checkout Session
# ==========================================================
@router.post("/create-checkout-session/{booking_id}")
def create_checkout_session(booking_id: int):
    db: Session = SessionLocal()

    try:
        booking = db.query(EventBooking).filter(
            EventBooking.id == booking_id
        ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if booking.status == "paid":
            raise HTTPException(status_code=400, detail="Booking already paid")

        # 🔥 Use actual booking amount (dynamic)
        amount_in_paise = int(booking.total_price * 100)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "inr",
                        "product_data": {
                            "name": f"Booking #{booking_id}"
                        },
                        "unit_amount": amount_in_paise,
                    },
                    "quantity": 1,
                }
            ],
            success_url="https://casemated-supercongested-loan.ngrok-free.dev/success",
            cancel_url="https://casemated-supercongested-loan.ngrok-free.dev/cancel",
            metadata={"booking_id": str(booking_id)},
        )

        return {"checkout_url": session.url}

    except HTTPException:
        raise

    except stripe.error.StripeError as e:
        message = getattr(e, "user_message", None) or str(e)
        raise HTTPException(status_code=400, detail=message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()


# ==========================================================
# ✅ Stripe Webhook
# ==========================================================
@router.post("/webhook")
async def stripe_webhook(request: Request):

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing stripe-signature header"},
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid payload"})
    except stripe.error.SignatureVerificationError:
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    # ======================================================
    # 🔥 Handle Successful Payment
    # ======================================================
    if event["type"] == "checkout.session.completed":

        session_data = event["data"]["object"]
        booking_id = session_data.get("metadata", {}).get("booking_id")

        if not booking_id:
            return {"status": "no_booking_id"}

        payment_intent_id = session_data.get("payment_intent")

        db: Session = SessionLocal()

        try:
            booking = db.query(EventBooking).filter(
                EventBooking.id == int(booking_id)
            ).first()

            if not booking:
                return {"status": "booking_not_found"}

            # 🔒 Idempotency protection
            existing_payment = db.query(Payment).filter(
                Payment.stripe_payment_intent == payment_intent_id
            ).first()

            if existing_payment:
                return {"status": "already_processed"}

            if booking.status == "paid":
                return {"status": "already_paid"}

            # ==================================================
            # Retrieve payment method details
            # ==================================================
            payment_method_type = None
            card_brand = None
            card_last4 = None

            if payment_intent_id:
                try:
                    intent = stripe.PaymentIntent.retrieve(
                        payment_intent_id,
                        expand=["charges"]
                    )

                    charges = intent.get("charges", {}).get("data", [])

                    if charges:
                        charge = charges[0]
                        details = charge.get("payment_method_details", {})

                        payment_method_type = details.get("type")

                        card_details = details.get("card", {})
                        card_brand = card_details.get("brand")
                        card_last4 = card_details.get("last4")

                except stripe.error.StripeError:
                    pass

            # ==================================================
            # Update Booking + Create Payment Record
            # ==================================================
            booking.status = "paid"

            payment = Payment(
                booking_id=int(booking_id),
                stripe_payment_intent=payment_intent_id,
                amount=session_data.get("amount_total", 0) / 100,
                currency=session_data.get("currency"),
                payment_method=payment_method_type,
                card_brand=card_brand,
                card_last4=card_last4,
                status="paid",
            )

            db.add(payment)
            db.commit()

            print("✅ PAYMENT STORED & BOOKING UPDATED:", booking_id)

        finally:
            db.close()

    return {"status": "success"}


# ==========================================================
# ✅ Get Payment Details
# ==========================================================
@router.get("/{booking_id}")
def get_payment_details(booking_id: int):

    db: Session = SessionLocal()

    try:
        payment = db.query(Payment).filter(
            Payment.booking_id == booking_id
        ).first()

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        return {
            "booking_id": payment.booking_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "card_brand": payment.card_brand,
            "card_last4": payment.card_last4,
            "status": payment.status,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        }

    finally:
        db.close()