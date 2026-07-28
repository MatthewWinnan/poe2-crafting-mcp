"""
Terminal value function — calculates the post-mod crafting value and cost.

Used by the optimizer to evaluate a finished item's total worth including
sockets, quality, runes, and corruption expected value.
"""

from __future__ import annotations

from poe2_crafting_mcp.crafting.simulator import ItemState, get_max_sockets_for_item_class


def calculate_terminal_value(
    item: ItemState,
    socket_value_per_slot: float = 50.0,
    quality_base_multiplier: float = 0.20,
    artificer_price: float = 5.0,
    quality_currency_price: float = 0.5,
    corruption_ev: float = 0.0,
) -> dict:
    """Calculate terminal (post-mod) value and cost for a crafted item.

    This is added to the optimizer's evaluation AFTER the mod strategy is found.
    It doesn't change which currency sequence is optimal — it's a fixed add-on.

    Args:
        item: the crafted item state (mods already finalized)
        socket_value_per_slot: avg value added per filled socket (chaos equivalent)
        quality_base_multiplier: how much quality adds as a fraction of item value
        artificer_price: cost per Artificer's Orb
        quality_currency_price: cost per Armourer's Scrap / Whetstone
        corruption_ev: expected value of Vaal Orb gamble (0 = don't corrupt)

    Returns dict with:
        - terminal_value: total value added by terminal steps
        - terminal_cost: total cost of terminal steps
        - breakdown: per-step details
    """
    max_sockets = item.max_sockets
    current_sockets = len(item.sockets)
    sockets_to_add = max(0, max_sockets - current_sockets)
    filled_sockets = len([s for s in item.sockets if s])

    # ── Socket value & cost ───────────────────────────────────────────────────
    # Value: each filled socket adds stats worth socket_value_per_slot
    # Assuming we'll fill all sockets with best runes
    total_socket_value = max_sockets * socket_value_per_slot
    socket_cost = sockets_to_add * artificer_price  # cost to open remaining sockets
    # Plus cost of the runes themselves (approximated as socket_value_per_slot / 2)
    rune_purchase_cost = max_sockets * (socket_value_per_slot * 0.5)

    # ── Quality value & cost ──────────────────────────────────────────────────
    quality_remaining = max(0, 20 - item.quality)
    quality_uses = quality_remaining // 5
    quality_cost = quality_uses * quality_currency_price
    # Quality value: % increase on base stats (hard to quantify generically)
    quality_value = quality_base_multiplier * 100  # approximate: 20% quality ≈ 20 chaos value

    # ── Corruption EV ─────────────────────────────────────────────────────────
    # EV is typically 0 for safe crafts, positive for gambles
    # Simplified: avg(nothing=0, reroll=-item_value, enchant=+enchant_value, socket=+socket_value)
    corruption_value = corruption_ev

    # ── Totals ────────────────────────────────────────────────────────────────
    terminal_value = total_socket_value + quality_value + corruption_value
    terminal_cost = socket_cost + rune_purchase_cost + quality_cost

    return {
        "terminal_value": round(terminal_value, 1),
        "terminal_cost": round(terminal_cost, 1),
        "net_terminal": round(terminal_value - terminal_cost, 1),
        "breakdown": {
            "sockets": {
                "max_sockets": max_sockets,
                "sockets_to_add": sockets_to_add,
                "value": round(total_socket_value, 1),
                "artificer_cost": round(socket_cost, 1),
                "rune_cost": round(rune_purchase_cost, 1),
            },
            "quality": {
                "current": item.quality,
                "target": 20,
                "uses_needed": quality_uses,
                "value": round(quality_value, 1),
                "cost": round(quality_cost, 1),
            },
            "corruption": {
                "ev": round(corruption_value, 1),
                "cost": 0,  # Vaal Orb price added by caller if used
            },
        },
    }
