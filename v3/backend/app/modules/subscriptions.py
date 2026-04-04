"""Subscription pricing, promo, and plan entitlement helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional

from fastapi import HTTPException

from .db import get_connection


def _normalize_promo_code(code: Optional[str]) -> str:
    return str(code or "").strip().upper()


def list_class_rates() -> List[Dict[str, object]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT class_name, annual_price_cents, currency, is_active
        FROM subscription_class_rates
        WHERE is_active=1
        ORDER BY CASE WHEN class_name='MyDocs' THEN 0 ELSE 1 END, class_name ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "class_name": row[0],
            "annual_price_cents": int(row[1]),
            "currency": row[2],
        }
        for row in rows
    ]


def get_plan_entitlements(plan_code: str) -> List[Dict[str, object]]:
    normalized = str(plan_code or "free").strip().lower() or "free"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT feature_key, enabled, hint_text
        FROM plan_feature_entitlements
        WHERE plan_code=?
        ORDER BY feature_key ASC
        """,
        (normalized,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "feature_key": row[0],
            "enabled": bool(row[1]),
            "hint": row[2],
        }
        for row in rows
    ]


def get_promotion(code: Optional[str]) -> Optional[Dict[str, object]]:
    normalized = _normalize_promo_code(code)
    if not normalized:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT code, discount_type, discount_value, description, is_active, expires_at
        FROM subscription_promotions
        WHERE code=?
        LIMIT 1
        """,
        (normalized,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row or not bool(row[4]):
        return None

    expires_at = row[5]
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.now(UTC):
                return None
        except Exception:
            return None

    return {
        "code": row[0],
        "discount_type": row[1],
        "discount_value": int(row[2]),
        "description": row[3],
    }


def quote_subscription(class_names: List[str], promo_code: Optional[str] = None) -> Dict[str, object]:
    normalized_classes = []
    seen = set()
    for class_name in class_names or []:
        cleaned = str(class_name or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_classes.append(cleaned)

    if not normalized_classes:
        raise HTTPException(status_code=400, detail="Select at least one class.")

    rates = {item["class_name"]: item for item in list_class_rates()}
    missing = [class_name for class_name in normalized_classes if class_name not in rates]
    if missing:
        raise HTTPException(status_code=404, detail=f"Class pricing not found for: {', '.join(missing)}")

    line_items = []
    subtotal = 0
    currency = rates[normalized_classes[0]]["currency"]
    for class_name in normalized_classes:
        item = rates[class_name]
        amount = int(item["annual_price_cents"])
        subtotal += amount
        line_items.append(
            {
                "class_name": class_name,
                "annual_price_cents": amount,
                "currency": item["currency"],
            }
        )

    promo = get_promotion(promo_code)
    discount = 0
    if promo:
        if promo["discount_type"] == "percent":
            discount = int(round(subtotal * (promo["discount_value"] / 100.0)))
        elif promo["discount_type"] == "fixed":
            discount = int(promo["discount_value"])
        discount = max(0, min(subtotal, discount))
    elif _normalize_promo_code(promo_code):
        raise HTTPException(status_code=400, detail="Promo code is invalid or expired.")

    total = max(0, subtotal - discount)
    return {
        "classes": line_items,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "total_cents": total,
        "currency": currency,
        "promo": promo,
        "billing_period": "annual",
    }


def list_active_user_classes(user_id: str) -> List[Dict[str, object]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT class_name, annual_price_cents, currency, promo_code, started_at, expires_at, auto_renew
        FROM user_class_subscriptions
        WHERE user_id=? AND status='ACTIVE'
        ORDER BY class_name ASC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "class_name": row[0],
            "annual_price_cents": int(row[1]),
            "currency": row[2],
            "promo_code": row[3],
            "started_at": row[4],
            "expires_at": row[5],
            "auto_renew": bool(row[6]),
        }
        for row in rows
    ]


def get_subscription_catalog() -> Dict[str, object]:
    return {
        "class_rates": list_class_rates(),
        "plans": {
            "free": {"entitlements": get_plan_entitlements("free")},
            "pro": {"entitlements": get_plan_entitlements("pro")},
            "premium": {"entitlements": get_plan_entitlements("premium")},
        },
        "promo_codes_supported": True,
        "billing_period": "annual",
    }


def activate_subscription(
    user_id: str,
    class_names: List[str],
    promo_code: Optional[str] = None,
    auto_renew: bool = False,
) -> Dict[str, object]:
    quote = quote_subscription(class_names, promo_code=promo_code)
    activated_at = datetime.now(UTC)
    expires_at = activated_at + timedelta(days=365)
    normalized_promo = _normalize_promo_code(promo_code) or None

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        for item in quote.get("classes", []):
            class_name = str(item.get("class_name") or "").strip()
            if not class_name:
                continue

            cursor.execute(
                """
                SELECT id
                FROM user_class_subscriptions
                WHERE user_id=? AND class_name=? AND status='ACTIVE'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, class_name),
            )
            existing = cursor.fetchone()

            row_values = (
                int(item.get("annual_price_cents") or 0),
                str(item.get("currency") or "INR"),
                normalized_promo,
                activated_at.isoformat(),
                expires_at.isoformat(),
                1 if auto_renew else 0,
            )

            if existing:
                cursor.execute(
                    """
                    UPDATE user_class_subscriptions
                    SET annual_price_cents=?,
                        currency=?,
                        promo_code=?,
                        started_at=?,
                        expires_at=?,
                        auto_renew=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (*row_values, int(existing[0])),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_class_subscriptions
                    (user_id, class_name, status, annual_price_cents, currency, promo_code, started_at, expires_at, auto_renew)
                    VALUES (?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, class_name, *row_values),
                )

        conn.commit()
    finally:
        conn.close()

    return {
        **quote,
        "auto_renew": bool(auto_renew),
        "activated_at": activated_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "active_classes": list_active_user_classes(user_id),
    }