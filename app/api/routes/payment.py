from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.stripe_config import stripe
from app.database import SessionLocal
from app.database import get_db
from app.models.caterer import Caterer
from app.models.user import User
from app.utils.auth import get_current_user
from app.models.event_booking import EventBooking
from app.models.payment import Payment
from fastapi.responses import FileResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import TableStyle
from reportlab.lib.styles import getSampleStyleSheet
import os

router = APIRouter(prefix="/api/payments", tags=["Payments"])


def _extract_payment_details(
    payment_intent_id: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:

    if not payment_intent_id:
        return None, None, None

    payment_method_type = None
    card_brand = None
    card_last4 = None

    intent = stripe.PaymentIntent.retrieve(
        payment_intent_id,
        expand=["latest_charge.payment_method_details", "payment_method"],
    )

    latest_charge = intent.get("latest_charge")

    if isinstance(latest_charge, dict):
        details = latest_charge.get("payment_method_details", {})
        payment_method_type = details.get("type")

        card_details = details.get("card", {})
        card_brand = card_details.get("brand")
        card_last4 = card_details.get("last4")

    if not card_last4:
        pm_data = intent.get("payment_method")
        if isinstance(pm_data, str):
            pm_data = stripe.PaymentMethod.retrieve(pm_data)

        if isinstance(pm_data, dict):
            payment_method_type = payment_method_type or pm_data.get("type")
            pm_card = pm_data.get("card", {})
            card_brand = card_brand or pm_card.get("brand")
            card_last4 = card_last4 or pm_card.get("last4")

    return payment_method_type, card_brand, card_last4


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
            raise HTTPException(404, "Booking not found")

        if booking.status == "paid":
            raise HTTPException(400, "Booking already paid")

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
            success_url="https://your-ngrok-url/success",
            cancel_url="https://your-ngrok-url/cancel",
            metadata={"booking_id": str(booking_id)},
            payment_intent_data={
                "metadata": {"booking_id": str(booking_id)}
            },
        )

        return {"checkout_url": session.url}

    finally:
        db.close()


# ==========================================================
# ✅ Stripe Webhook
# ==========================================================
@router.post("/webhook")
async def stripe_webhook(request: Request):

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid webhook"})

    if event["type"] == "checkout.session.completed":

        session_data = event["data"]["object"]
        payment_intent_id = session_data.get("payment_intent")
        booking_id = session_data.get("metadata", {}).get("booking_id")

        if not booking_id:
            return {"status": "no_booking_id"}

        db: Session = SessionLocal()

        try:
            booking = db.query(EventBooking).filter(
                EventBooking.id == int(booking_id)
            ).first()

            if not booking:
                return {"status": "booking_not_found"}

            existing_payment = db.query(Payment).filter(
                Payment.stripe_payment_intent == payment_intent_id
            ).first()

            if existing_payment:
                return {"status": "already_processed"}

            payment_method_type, card_brand, card_last4 = \
                _extract_payment_details(payment_intent_id)

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

        finally:
            db.close()

    return {"status": "success"}

    # ======================================================
    # 🔥 Handle Successful Payment
    # ======================================================
    if event["type"] == "checkout.session.completed":

        session_data = event["data"]["object"]
        payment_intent_id = session_data.get("payment_intent")
        booking_id = session_data.get("metadata", {}).get("booking_id")
        booking_id = booking_id or session_data.get("client_reference_id")

        if not booking_id and payment_intent_id:
            try:
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                booking_id = intent.get("metadata", {}).get("booking_id")
            except stripe.error.StripeError:
                pass

        if not booking_id:
            return {"status": "no_booking_id"}

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
                try:
                    (
                        payment_method_type,
                        card_brand,
                        card_last4,
                    ) = _extract_payment_details(payment_intent_id)
                except stripe.error.StripeError:
                    payment_method_type, card_brand, card_last4 = None, None, None

                updated_existing = False
                if not existing_payment.payment_method and payment_method_type:
                    existing_payment.payment_method = payment_method_type
                    updated_existing = True
                if not existing_payment.card_brand and card_brand:
                    existing_payment.card_brand = card_brand
                    updated_existing = True
                if not existing_payment.card_last4 and card_last4:
                    existing_payment.card_last4 = card_last4
                    updated_existing = True

                if updated_existing:
                    db.commit()
                    return {"status": "already_processed_updated"}

                return {"status": "already_processed"}

            # ==================================================
            # Retrieve payment method details
            # ==================================================
            payment_method_type = None
            card_brand = None
            card_last4 = None

            if payment_intent_id:
                try:
                    (
                        payment_method_type,
                        card_brand,
                        card_last4,
                    ) = _extract_payment_details(payment_intent_id)
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
            try:
                db.commit()
            except Exception as exc:
                db.rollback()
                return {"status": "db_error", "error": str(exc)}

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

# ==========================================================
# 💳 GET CATERER PAYMENT HISTORY
# ==========================================================
@router.get("/caterer/history")
def get_caterer_payment_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(status_code=403, detail="Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")

    payments = (
        db.query(Payment, EventBooking)
        .join(EventBooking, EventBooking.id == Payment.booking_id)
        .filter(EventBooking.caterer_id == caterer.id)
        .order_by(Payment.paid_at.desc())
        .all()
    )

    result = []

    for payment, booking in payments:
        result.append({
            "booking_id": booking.id,
            "event_id": booking.event_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "card_brand": payment.card_brand,
            "card_last4": payment.card_last4,
            "status": payment.status,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None
        })

    return result

# ==========================================================
# 🔁 REFUND PAYMENT
# ==========================================================
@router.post("/refund/{booking_id}")
def refund_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "paid":
        raise HTTPException(status_code=400, detail="Only paid bookings can be refunded")

    payment = db.query(Payment).filter(
        Payment.booking_id == booking_id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    try:
        refund = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent
        )

        booking.status = "refunded"
        payment.status = "refunded"

        db.commit()

        return {
            "message": "Refund successful",
            "refund_id": refund["id"]
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/invoice/{booking_id}")
def download_invoice(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    # Validate booking
    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    payment = db.query(Payment).filter(
        Payment.booking_id == booking_id,
        Payment.status == "paid"
    ).first()

    if not payment:
        raise HTTPException(status_code=400, detail="Invoice only for paid bookings")

    # Get caterer & organizer
    caterer = db.query(Caterer).filter(
        Caterer.id == booking.caterer_id
    ).first()

    organizer = db.query(User).filter(
        User.id == booking.organizer_id
    ).first()

    file_path = f"invoice_{booking_id}.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>INVOICE</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    data = [
        ["Invoice No:", f"INV-{booking_id}"],
        ["Booking ID:", booking_id],
        ["Event ID:", booking.event_id],
        ["Caterer:", caterer.business_name if caterer else ""],
        ["Organizer ID:", organizer.id if organizer else ""],
        ["Amount Paid:", f"₹{payment.amount}"],
        ["Payment Method:", payment.payment_method or ""],
        ["Card:", f"{payment.card_brand} •••• {payment.card_last4}"],
        ["Payment Date:", payment.paid_at.strftime("%d %b %Y %I:%M %p")]
    ]

    table = Table(data, colWidths=[2.5 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)

    doc.build(elements)

    return FileResponse(
        path=file_path,
        filename=file_path,
        media_type="application/pdf"
    )