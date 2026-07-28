# Research: Omen Stacking Rules & Abyss Crafting Model

## Omen Stacking — CONFIRMED (source: Mobalytics omen-crafting guide)

### Rule: Multiple omens CAN be active simultaneously and stack effects

> "Omens can also be used in combination to stack their effects"

### Confirmed Combos:
- **Dextral Exaltation + Greater Exaltation** → adds 2 suffix mods (both min_lv from currency tier)
- **Homogenising Exaltation + Dextral Exaltation** → exalt adds suffix that shares tags with existing mods
- By extension: **Sinistral Exaltation + Greater Exaltation** → adds 2 prefix mods

### Stacking Mechanics:
- Each omen contributes its effect independently
- `gentype_only` (prefix/suffix targeting) + `qty_override` (add 2) stack
- `gentype_only` + `homogenise` (tag matching) stack
- Multiple omens consumed on the single currency use

### Architecture Change Needed:
Current: `apply_currency(currency, omen="single_omen")`
Needed: `apply_currency(currency, omens=["omen1", "omen2", ...])`

Merge logic: combine all effects from active omens into one effective set:
- gentype_only: take from whichever omen specifies it (1=prefix, 2=suffix)
- del_gentype_only: same
- qty_override: take from Greater Exaltation if present
- homogenise: True if any omen has it
- del_target: "lowest_req_level" if Whittling present

---

## Full Omen List (0.5.4, from Mobalytics + poe2db)

### Crafting Omens (model in simulator):
| Omen | Affects | Effect |
|------|---------|--------|
| Sinistral Exaltation | Exalted Orb | Add only prefix |
| Dextral Exaltation | Exalted Orb | Add only suffix |
| Greater Exaltation | Exalted Orb | Add 2 mods instead of 1 |
| Homogenising Exaltation | Exalted Orb | Add mod sharing tags with existing |
| Catalysing Exaltation | Exalted Orb | Consume catalyst quality → bias weights |
| Sinistral Annulment | Annulment | Remove only prefix |
| Dextral Annulment | Annulment | Remove only suffix |
| Sinistral Erasure | Chaos Orb | Remove only prefix |
| Dextral Erasure | Chaos Orb | Remove only suffix |
| Whittling | Chaos Orb | Remove lowest req_level mod (deterministic) |
| Sinistral Crystallisation | Perfect/Corrupted Essence | Remove only prefix |
| Dextral Crystallisation | Perfect/Corrupted Essence | Remove only suffix |
| Homogenising Coronation | Regal Orb | Add mod sharing tags with existing |
| Sinistral Coronation | Regal Orb | Add only prefix (implied, not confirmed) |
| Dextral Coronation | Regal Orb | Add only suffix (implied, not confirmed) |
| Sinistral Alchemy | Alchemy Orb | Maximize prefixes |
| Dextral Alchemy | Alchemy Orb | Maximize suffixes |

### Terminal/Non-currency Omens (model as decision, not pool roll):
| Omen | Effect |
|------|--------|
| Omen of Corruption | Vaal Orb always results in change (no "nothing" outcome) |
| Omen of the Ancients | Orb of Chance → random Unique of same item CLASS |
| Omen of Chance | Orb of Chance → Unique of exact same base type |
| Omen of Sanctification | Divine Orb sanctifies (80-120% rolls, locks item permanently) |
| Omen of the Blessed | Divine Orb only rerolls implicit mods |
| Omen of Recombination | Recombination is "lucky" (rolls twice, picks best) |

### Abyss Omens (separate crafting system — see below):
| Omen | Effect |
|------|--------|
| Sinistral Necromancy | Desecration adds only prefix |
| Dextral Necromancy | Desecration adds only suffix |
| Omen of Light | Annulment removes only desecrated mods |
| Omen of Abyssal Echoes | Reveal gives reroll (6 choices instead of 3) |
| Omen of Putrefaction | Replaces ALL mods with up to 6 desecrated + corrupts |
| Omen of the Blackblooded | Desecration guarantees Kurgal mod |
| Omen of the Liege | Desecration guarantees Amanamu mod |
| Omen of the Sovereign | Desecration guarantees Ulaman mod |

---

## Abyss Crafting — Separate Engine Model Needed

### How it differs from regular crafting:
Regular: `apply_currency → random outcome from pool`
Abyss: `apply_bone → reveal 3 options from desecrated pool → PLAYER CHOOSES`

### Steps:
1. **Apply bone** (Gnawed Rib, Ancient Jawbone, etc.) → adds UNREVEALED desecrated slot
2. **Go to Well of Souls** → reveals 3 random options from desecrated pool
3. **Player picks 1 of 3** (or with Echoes omen: picks 1 of 6)
4. Mod placed on item (occupies a normal prefix/suffix slot)

### Bone types (determine item class):
- Altered Collarbone → Jewellery (Amulet, Ring, Belt)
- Gnawed Rib (max ilvl 64) / Ancient Rib / Preserved Rib (min 40) → Armour
- Gnawed Jawbone (max 64) / Preserved Jawbone / Ancient Jawbone (min 40) → Weapons
- Preserved Cranium → Jewels
- Preserved Vertebrae → Waystones

### Modeling for the optimizer:
The optimizer can't "simulate" abyss crafting the same way because the player
has AGENCY in the choice. Options:

1. **Expected value model**: calculate P(target mod in 3 revealed) and
   P(target mod in 6 revealed with Echoes). The "action" has a probability
   of success per attempt, like exalting but with better odds due to choice.

2. **Conditional model**: the optimizer says "use desecration on this slot"
   and we calculate the probability that AT LEAST ONE of the 3 (or 6) revealed
   mods is the target. If yes → pick it (deterministic). If no → wasted bone.

3. **Pool narrowing**: Lich omens (Blackblooded/Liege/Sovereign) guarantee a
   specific boss's mod pool — much smaller pool, much higher hit rate.

### Data we have:
- `mod_weights WHERE pool='desecrated'` — full desecrated mod pool with weights
- Can calculate P(target in 3 draws from weighted pool without replacement)

### Integration with optimizer:
The rule-list GP can have an action like:
```
THEN desecrate(bone_type, target_family, omen=None)
```
The fitness evaluation computes: P(hitting target) = 1 - P(miss all 3 draws)
Cost per attempt: bone_price + omen_price (if used)
Expected attempts: 1 / P(success)

This is analogous to how we model exalt (P per attempt × cost per attempt)
but with much better odds due to the 3-choice mechanic.
