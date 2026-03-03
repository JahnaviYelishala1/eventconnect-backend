import argparse
from typing import Optional, Tuple

from sqlalchemy import or_

from app.core.stripe_config import stripe
from app.database import SessionLocal
from app.models.payment import Payment


def extract_card_fields(payment_intent_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    payment_method_type = None
    card_brand = None
    card_last4 = None

    intent = stripe.PaymentIntent.retrieve(
        payment_intent_id,
        expand=[
            "latest_charge.payment_method_details",
            "payment_method",
        ],
    )

    latest_charge = intent.get("latest_charge")
    if isinstance(latest_charge, dict):
        details = latest_charge.get("payment_method_details", {})
        payment_method_type = details.get("type")

        card_details = details.get("card", {})
        card_brand = card_details.get("brand")
        card_last4 = card_details.get("last4")

    # Fallback when card data is not present on latest_charge.
    if not card_last4 or not card_brand or not payment_method_type:
        pm_data = intent.get("payment_method")
        if isinstance(pm_data, str):
            pm_data = stripe.PaymentMethod.retrieve(pm_data)

        if isinstance(pm_data, dict):
            payment_method_type = payment_method_type or pm_data.get("type")
            pm_card = pm_data.get("card", {})
            card_brand = card_brand or pm_card.get("brand")
            card_last4 = card_last4 or pm_card.get("last4")

    return payment_method_type, card_brand, card_last4


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing payment card details from Stripe."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without writing to database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of payment rows to scan (0 = no limit).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Commit every N updated rows.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    total = 0
    updated = 0
    skipped = 0
    errors = 0
    pending_commits = 0

    try:
        query = (
            db.query(Payment)
            .filter(Payment.stripe_payment_intent.isnot(None))
            .filter(Payment.stripe_payment_intent != "")
            .filter(
                or_(
                    Payment.payment_method.is_(None),
                    Payment.payment_method == "",
                    Payment.card_brand.is_(None),
                    Payment.card_brand == "",
                    Payment.card_last4.is_(None),
                    Payment.card_last4 == "",
                )
            )
            .order_by(Payment.id.asc())
        )

        if args.limit and args.limit > 0:
            query = query.limit(args.limit)

        payments = query.all()
        total = len(payments)
        print(f"Rows matched: {total}")

        for payment in payments:
            try:
                payment_method_type, card_brand, card_last4 = extract_card_fields(
                    payment.stripe_payment_intent
                )
            except stripe.error.StripeError as exc:
                errors += 1
                print(
                    f"[stripe_error] payment_id={payment.id} intent={payment.stripe_payment_intent} error={exc}"
                )
                continue
            except Exception as exc:
                errors += 1
                print(
                    f"[error] payment_id={payment.id} intent={payment.stripe_payment_intent} error={exc}"
                )
                continue

            changed = False
            if not payment.payment_method and payment_method_type:
                payment.payment_method = payment_method_type
                changed = True
            if not payment.card_brand and card_brand:
                payment.card_brand = card_brand
                changed = True
            if not payment.card_last4 and card_last4:
                payment.card_last4 = card_last4
                changed = True

            if not changed:
                skipped += 1
                continue

            updated += 1
            if args.dry_run:
                print(
                    f"[dry_run] payment_id={payment.id} method={payment_method_type} brand={card_brand} last4={card_last4}"
                )
                continue

            pending_commits += 1
            if pending_commits >= args.batch_size:
                db.commit()
                pending_commits = 0

        if not args.dry_run and pending_commits > 0:
            db.commit()

        print("----- Summary -----")
        print(f"matched={total}")
        print(f"updated={updated}")
        print(f"skipped_no_new_data={skipped}")
        print(f"errors={errors}")
        print(f"dry_run={args.dry_run}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
