# Terminal Value Steps — Post-Mod Crafting

These are crafting steps that happen AFTER the mod optimization is complete.
They don't affect the GP's decision-making about which mods to pursue — they
add deterministic known value to a finished item.

The optimizer's fitness function should account for these as a fixed cost/benefit
added to the final item evaluation, not as branching decisions in the rule-list.

## 1. Sockets (Artificer's Orb)

**What:** Each Artificer's Orb adds or improves a socket on the item.
Items can have 1-3 sockets (depending on base type and RNG).

**Why it matters for value:**
- Each socket holds a Rune or Soul Core that adds stats
- Essence of Horror gives "60% increased effect of Socketed Augment Items"
  → socket count is a multiplier on that mod's power
- More sockets = strictly more power (no downside)

**Model as terminal step:**
- Cost: N × Artificer's Orb price (each attempt adds/improves one socket)
- Value: known based on which runes/soul cores the build wants to socket
- The optimizer doesn't need to decide WHEN to socket — it's always last

## 2. Quality (Armourer's Scrap / Blacksmith's Whetstone)

**What:** +5% quality per use, up to 20% (23% if corrupted with lucky outcome).
Quality increases base defences/damage by a percentage.

**Model as terminal step:**
- Cost: 4 × Scrap/Whetstone price (always go to 20%)
- Value: flat multiplier on base stats (known from base type)
- Always applied, no decision needed

## 3. Rune Socketing

**What:** Place a Rune or Soul Core into an open socket.
Effects depend on the rune and the item slot.

**Model as terminal step:**
- Cost: rune price (from poe.ninja)
- Value: known stats from the rune (flat life, resistance, etc.)
- Build-dependent (optimizer doesn't choose runes — PoB eval tells us value)

## 4. Delirium (Distilled Emotions) — Jewels & Amulets

**What:**
- Jewels: Distilled Emotion removes a mod and adds a guaranteed modifier
- Amulets: Instil at Decanter of Madness → adds a Notable passive from tree

**For jewels:** This IS part of the crafting decision (which mod to sacrifice,
which emotion to use). Should be modeled like essence (remove + add guaranteed).
This is a CRAFTING step, not terminal — the GP should consider it.

**For amulets:** The anoint is terminal — it's always the last step and adds
a known notable passive. Cost = emotion price. Value = PoB DPS from that notable.

## 5. Corruption (Vaal Orb)

**What:** Final gamble step. Outcomes: nothing, brick, enchant, socket, divine.
Omen of Corruption removes the "nothing" outcome.

**Model as terminal step:**
- Cost: Vaal Orb price (+ Omen of Corruption if used)
- Value: EV calculation based on outcome probabilities
- Always the VERY LAST step (item can't be modified after)

## 6. Sanctification (Divine + Omen of Sanctification)

**What:** Rerolls all mod values to 80-120% of normal range. Locks item permanently.

**Model as terminal step:**
- Cost: Divine Orb + Omen of Sanctification price
- Value: EV of improved rolls (on average positive, but variance)
- Only used on GG items where the value justifies the lock

---

## Integration with Optimizer

The optimizer's fitness function computes:

```
total_item_value = mod_value (from PoB DPS simulation)
                 + socket_value (N sockets × avg rune value)
                 + quality_bonus (known % increase on base)
                 + anoint_value (if amulet, known notable DPS)

total_cost = crafting_cost (from optimizer)
           + terminal_cost (sockets + quality + runes + corruption)

verdict = total_item_value vs trade_price
```

The GP optimizes only the `crafting_cost` part. Terminal costs are fixed
and added at evaluation time.

Exception: Delirium jewel crafting is NOT terminal — it's a core crafting
mechanic for jewels (like essences). Should be modeled as a crafting action.
