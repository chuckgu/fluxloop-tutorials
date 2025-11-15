from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

import fluxloop
from langchain_core.tools import tool

from .base import connect, rows_to_dicts


@tool
@fluxloop.trace(name="search_car_rentals")
def search_car_rentals(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """Search for car rentals based on location, name, and price tier."""
    query = "SELECT * FROM car_rentals WHERE 1=1"
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
    if start_date:
        query += " AND (start_date IS NULL OR start_date >= ?)"
        params.append(start_date)
    if end_date:
        query += " AND (end_date IS NULL OR end_date <= ?)"
        params.append(end_date)

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return rows_to_dicts(cursor, rows)


@tool
@fluxloop.trace(name="book_car_rental")
def book_car_rental(rental_id: int) -> str:
    """Book a car rental by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE car_rentals SET booked = 1 WHERE id = ?", (rental_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully booked."
        return f"No car rental found with ID {rental_id}."


@tool
@fluxloop.trace(name="update_car_rental")
def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> str:
    """Update a car rental's start and end dates."""
    with connect() as conn:
        cursor = conn.cursor()
        if start_date:
            cursor.execute(
                "UPDATE car_rentals SET start_date = ? WHERE id = ?",
                (start_date, rental_id),
            )
        if end_date:
            cursor.execute(
                "UPDATE car_rentals SET end_date = ? WHERE id = ?",
                (end_date, rental_id),
            )
        conn.commit()
        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully updated."
        return f"No car rental found with ID {rental_id}."


@tool
@fluxloop.trace(name="cancel_car_rental")
def cancel_car_rental(rental_id: int) -> str:
    """Cancel a car rental by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE car_rentals SET booked = 0 WHERE id = ?", (rental_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully cancelled."
        return f"No car rental found with ID {rental_id}."

