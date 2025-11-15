from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from .base import connect, rows_to_dicts


@tool
def search_trip_recommendations(
    location: Optional[str] = None,
    name: Optional[str] = None,
    keywords: Optional[str] = None,
) -> list[dict]:
    """Search for trip recommendations based on location, name, and keywords."""
    query = "SELECT * FROM trip_recommendations WHERE 1=1"
    params: list = []

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if keywords:
        keyword_list = [keyword.strip() for keyword in keywords.split(",")]
        keyword_conditions = " OR ".join(["keywords LIKE ?" for _ in keyword_list])
        query += f" AND ({keyword_conditions})"
        params.extend([f"%{keyword}%" for keyword in keyword_list])

    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return rows_to_dicts(cursor, rows)


@tool
def book_excursion(recommendation_id: int) -> str:
    """Book an excursion by its recommendation ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trip_recommendations SET booked = 1 WHERE id = ?",
            (recommendation_id,),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return f"Trip recommendation {recommendation_id} successfully booked."
        return f"No trip recommendation found with ID {recommendation_id}."


@tool
def update_excursion(recommendation_id: int, details: str) -> str:
    """Update a trip recommendation's details by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trip_recommendations SET details = ? WHERE id = ?",
            (details, recommendation_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return f"Trip recommendation {recommendation_id} successfully updated."
        return f"No trip recommendation found with ID {recommendation_id}."


@tool
def cancel_excursion(recommendation_id: int) -> str:
    """Cancel a trip recommendation by its ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trip_recommendations SET booked = 0 WHERE id = ?",
            (recommendation_id,),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return f"Trip recommendation {recommendation_id} successfully cancelled."
        return f"No trip recommendation found with ID {recommendation_id}."

