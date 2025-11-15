from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

import fluxloop
from langchain_core.tools import tool

from .base import connect, rows_to_dicts


@tool
@fluxloop.trace(name="search_hotels")
def search_hotels(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """Search for hotels based on location, name, and price tier."""
    query = "SELECT * FROM hotels WHERE 1=1"
    params: list = []

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if price_tier:
        query += " AND price_tier = ?"
        params.append(price_tier)
    if checkin_date:
        query += " AND (checkin_date IS NULL OR checkin_date >= ?)"
        params.append(checkin_date)
    if checkout_date:
        query += " AND (checkout_date IS NULL OR checkout_date <= ?)"
        params.append(checkout_date)

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return rows_to_dicts(cursor, rows)


@tool
@fluxloop.trace(name="book_hotel")
def book_hotel(hotel_id: int) -> str:
    """Book a hotel by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hotels SET booked = 1 WHERE id = ?", (hotel_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return f"Hotel {hotel_id} successfully booked."
        return f"No hotel found with ID {hotel_id}."


@tool
@fluxloop.trace(name="update_hotel")
def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> str:
    """Update a hotel's check-in and check-out dates."""
    with connect() as conn:
        cursor = conn.cursor()
        if checkin_date:
            cursor.execute(
                "UPDATE hotels SET checkin_date = ? WHERE id = ?",
                (checkin_date, hotel_id),
            )
        if checkout_date:
            cursor.execute(
                "UPDATE hotels SET checkout_date = ? WHERE id = ?",
                (checkout_date, hotel_id),
            )
        conn.commit()
        if cursor.rowcount > 0:
            return f"Hotel {hotel_id} successfully updated."
        return f"No hotel found with ID {hotel_id}."


@tool
@fluxloop.trace(name="cancel_hotel")
def cancel_hotel(hotel_id: int) -> str:
    """Cancel a hotel by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hotels SET booked = 0 WHERE id = ?", (hotel_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return f"Hotel {hotel_id} successfully cancelled."
        return f"No hotel found with ID {hotel_id}."

