# Phase 3: Crafting Strategy Research

This document catalogs every viable PoE2 crafting path, the decision points
within each, and the conditions under which each path is optimal. This
research directly produces:

1. **Seed rule-lists** for the optimizer's initial population
2. **Condition predicates** for the rule-list vocabulary
3. **Understanding of when each strategy wins** to validate optimizer output

---

## Part 1: Complete Strategy Catalog

### Strategy 1: Alt-Spam → Regal → Exalt Fill

The bread-and-butter approach. Cheapest path to a single target mod.

```
Phase A — Fishing (Magic):
  Normal → Transmute → got target? → NO: Alteration (repeat)
                                   → YES: phase B

Phase B — Transition to Rare:
  Magic with target, 1 mod → Augment (adds 1) → Regal (→ Rare, adds 1) = 3 mods
  Magic with target, 2 mods → Regal (→ Rare, adds 1) = 3 mods

Phase C — Fill remaining slots:
  Rare with target + 2 random → Exalt → Exalt → Exalt (fill to 6)
  At each exalt: if hit another target, great. If junk, evaluate annul.
```

**Key decision points:**
- Transmute vs Alteration for fishing? Alt rerolls in-place (no scour needed),
  gives 1-2 mods per use. Transmute needs scour between misses. Alt is almost
  always better unless scour is essentially free.
- Skip augment? Regal adds 1 mod to a 1-mod Magic item just fine. Augment
  fills the other affix type — if that pool is bad (all junk suffixes), skip
  aug and save the currency. The GA should discover this.
- Greater/Perfect transmute for fishing? Narrows pool dramatically. If target
  is T1 (req_level 70+), perfect_transmute eliminates all low-tier mods.
  Cost per attempt is higher but hit rate is higher. Break-even depends on
  the specific pool size ratio.

**When this wins:** 1-2 target mods, targets have decent weight in pool,
currencies are cheap.

**When this loses:** 3+ target mods (exalt fill is too random), targets have
very low weight (chaos spam might be comparable).

---

### Strategy 2: Chaos Spam

Brute force. Chaos removes 1 mod + adds 1 mod on a Rare item. NOT a full
reroll — it's a single swap per chaos orb.

```
Normal → Alchemy (→ Rare, 4 mods) → Chaos → Chaos → Chaos → ...
Check after each chaos: all targets present?
```

**Critical mechanic:** PoE2 Chaos Orb removes 1 random mod and adds 1 random
mod. This is NOT PoE1's "reroll all mods." You're iteratively swapping one
mod at a time on a rare item. This means:

- If you have 4 mods including 2 targets, chaos has 2/4 chance to remove a
  target (50% chance of bricking your progress).
- The more targets you have on the item, the MORE dangerous chaos is.
- Chaos is only "safe" when you have 0 targets (nothing to lose).

**This changes when chaos is viable:** it's really only good when you want
to reroll an item with no good mods, hoping to randomly land multiple targets.
For items with partial progress, chaos is destructive.

**Variants:**
- Greater chaos (min_lv 35): only adds mods ilvl 35+, but removal is still
  random from ALL mods. Useful for adding higher-tier mods.
- Perfect chaos (min_lv 50): same principle, even more restricted add pool.
- Omen of Sinistral/Dextral Erasure: controls WHICH mod is removed (prefix
  or suffix only). This is huge — if your targets are all prefixes, dextral
  erasure means chaos can only remove suffixes. Dramatically safer.

**When this wins:** Targets are very common in pool (high combined weight),
you need 2+ of them, and you don't mind high variance.

**When this loses:** Almost always loses to alt-regal for 1 target. Loses
to essence for 2 targets when one has an essence.

---

### Strategy 3: Essence Crafting

Essences guarantee one specific mod. The rest fills randomly. Two tiers:

- **Greater Essence**: used on Magic item → becomes Rare with guaranteed mod
  + 3 random mods (4 total).
- **Perfect Essence**: used on Rare item → rerolls all non-fractured mods,
  guarantees one mod + fills rest randomly.

```
Phase A — Apply essence:
  Normal → Transmute → Magic → Greater Essence → Rare (4 mods, 1 guaranteed)
  OR: Normal → Alchemy → Rare → Perfect Essence → Rare (rerolled, 1 guaranteed)

Phase B — Evaluate:
  If guaranteed mod + another target hit → great, exalt fill
  If guaranteed mod + all junk → annul junk? Or perfect essence again?

Phase C — Fill / Fix:
  Exalt for remaining targets, annul junk, or re-essence
```

**Key decision points:**
- Greater vs Perfect essence? Greater is cheaper, used on magic. Perfect is
  more expensive, used on rare (rerolls everything). If you have a fractured
  mod you want to keep, perfect essence respects it (keeps fractured mods).
- Omen of Sinistral/Dextral Crystallisation: controls which mods are KEPT
  during essence application. Sinistral keeps prefixes, dextral keeps suffixes.
  This is extremely powerful: essence + omen = guarantee 1 mod while
  preserving existing prefixes or suffixes.
- Re-essence vs annul+exalt: if essence gave guaranteed mod + 3 junk,
  is it cheaper to re-essence (reroll all but guaranteed) or to annul
  the junk one by one and exalt replacements?

**When this wins:** Target mod has very low weight in normal pool (or is
essence-only, weight 0). Target mod has an essence that guarantees it. One
target is hard to hit, rest are common.

**When this loses:** All targets are common (alt-spam cheaper). Essence is
very expensive relative to the probability gain.

---

### Strategy 4: Fracture-First (Buy from Trade)

Not a crafting path per se — it's a starting point. Buy a fractured item from
trade with one target mod permanently locked, then craft the remaining slots.

```
BUY_FRACTURED(hardest_target_family) → Rare with 1 fractured mod
Phase A — Fill remaining:
  Exalt remaining open slots
  Annul non-target mods if needed
  Divine values within tiers
```

**Key decision points:**
- Which mod to fracture? Always the hardest/rarest target. If T1 ES has 2%
  chance per exalt, buy it fractured and skip hundreds of expected attempts.
- Fracture cost vs craft cost: if a fractured T1 ES Gold Gloves costs 200c
  on trade, but crafting T1 ES from scratch has expected cost 150c, don't
  buy fractured. The pre-flight price cache answers this automatically.
- Crafting on a fractured base: the fractured mod occupies 1 of 3 prefix
  or suffix slots permanently. Plan the remaining 5 slots around it.

**When this wins:** Hardest target has very low weight AND fractured bases
are available at reasonable price on trade.

**When this loses:** Fractured bases are overpriced, or target is easy to hit
naturally.

---

### Strategy 5: Omen-Targeted Actions

Omens modify the next currency use. They're one-shot consumables with their
own trade price. The key omens for crafting:

```
Prefix/Suffix targeting:
  Sinistral Exaltation   → exalt adds a PREFIX only
  Dextral Exaltation     → exalt adds a SUFFIX only
  Sinistral Coronation   → regal adds a PREFIX only
  Dextral Coronation     → regal adds a SUFFIX only
  Sinistral Annulment    → annul removes a PREFIX only
  Dextral Annulment      → annul removes a SUFFIX only

Chaos protection:
  Sinistral Erasure      → chaos removes a PREFIX only (protect suffixes)
  Dextral Erasure        → chaos removes a SUFFIX only (protect prefixes)
  Omen of Whittling      → chaos removes the LOWEST req_level mod (deterministic)

Alchemy targeting:
  Sinistral Alchemy      → alchemy maximizes prefixes (3P + 1S)
  Dextral Alchemy        → alchemy maximizes suffixes (1P + 3S)

Essence protection:
  Sinistral Crystallisation → essence keeps existing prefixes
  Dextral Crystallisation   → essence keeps existing suffixes
```

**Omens are not a standalone strategy** — they modify other strategies. The
optimizer should discover WHEN an omen is worth its cost by trying the same
strategy with and without omens and comparing total expected cost.

**Key decision points:**
- Omen cost vs probability gain: sinistral exalt on a pool with 60% prefixes
  gives less benefit than on a pool with 30% prefixes. The narrower the
  natural prefix ratio, the more valuable sinistral is.
- Omen + annul for surgical removal: dextral annulment on an item with 2
  target prefixes + 1 junk suffix = 100% chance to remove the junk. Without
  omen, 1/3 chance (might destroy a target). Worth it if omen cost < 2x annul.
- Stacking omens with greater/perfect: sinistral + greater_exalted = only
  prefixes with min_lv 35. Double narrowing.

**When this wins:** Pool has strong prefix/suffix imbalance and targets are
concentrated on one side. Annul situations with valuable mods at risk.

**When this loses:** Omen is expensive relative to the probability improvement.
Targets are evenly split between prefix and suffix.

---

### Strategy 6: Annul-Exalt Cycling

When you have some target mods + junk, try to remove junk without destroying
targets. High risk, high reward.

```
Rare with: [Target_A, Target_B, Junk_C, Junk_D]

Annul: 1/4 chance each mod.
  If removes Junk_C or Junk_D (50%): → now have [Target_A, Target_B, Junk_X]
    Annul again: 1/3 chance each. Removes junk (33%): → [Target_A, Target_B]
    Exalt: rolls from pool with A,B families blocked. Hope for Target_C.
  If removes Target_A or Target_B (50%): BRICKED → scour and restart
```

**The risk math:**
- With N mods total, T targets, J junk: P(annul hits junk) = J/N
- This is favorable only when J > T (more junk than targets)
- With omen (sinistral/dextral annulment): can guarantee removal from
  the right affix type if all junk is prefix and all targets are suffix
  (or vice versa)

**Key decision points:**
- removable_gt_targets: only annul when junk count > target count
  (more likely to hit junk than target)
- Omen annul when junk and targets are on the same side (all prefixes):
  omen doesn't help. Only helps when they're on different sides.
- When to give up and scour: after losing a target to annul, is it
  cheaper to scour and restart or try to re-exalt the lost target?

**When this wins:** Item has 2+ targets already hit, 1-2 junk mods, and
especially when junk and targets are on different affix sides (omen annul).

**When this loses:** Junk count <= target count (coin flip or worse).
All mods on same side (omen doesn't help).

---

### Strategy 7: Buy-Magic Shortcut

Skip the alt-spam phase entirely by buying a Magic item with the target mod
already on it from trade.

```
BUY_MAGIC(target_family) → Magic with 1-2 mods including target
  → Regal → Rare (3 mods) → Exalt fill
```

**Key decision points:**
- Cost comparison: if alt-spam expected cost for target is 30c (300 alts @
  0.1c each), and a Magic item with that mod costs 25c on trade, buy it.
  If magic item costs 50c, craft it yourself.
- The pre-flight cache fetches these prices automatically.

**When this wins:** Target mod is rare (low weight), alt-spam would take
hundreds of attempts, but magic items with the mod are available on trade
because other players ID'd and listed them.

**When this loses:** Target mod is common (alt-spam is cheap), or magic items
with the mod aren't listed / are overpriced.

---

### Strategy 8: Alchemy Slam

Skip the transmute→aug→regal chain. Go straight to rare with 4 mods.

```
Normal → Alchemy → Rare (4 mods) → evaluate
  If any targets hit: exalt fill, annul junk
  If no targets: scour → alchemy again
```

**Compared to alt-regal:**
- Alchemy gives 4 mods at once — 4 chances to hit targets
- But costs more than transmute and doesn't let you control which mod
  is the "anchor" (you can't fish for a specific first mod)
- With omen of sinistral/dextral alchemy: can force 3P+1S or 1P+3S

**When this wins:** Multiple targets, all relatively common. Alchemy is
cheaper than expected alt-spam + regal combined.

**When this loses:** You need a specific rare mod as anchor — alchemy can't
fish for it. Single-target crafting.

---

### Strategy 9: Flux Orb Conversion

Post-craft step. Convert resistance mods between elements.

```
Craft item with any T1 resistance → Flux orb to convert to desired element
  Blazing Flux: Cold+Lightning → Fire
  Chilling Flux: Fire+Lightning → Cold
  Crackling Flux: Fire+Cold → Lightning
  Void Flux: all elemental → Chaos
```

**This is a modifier to other strategies**, not standalone. The optimizer
should treat flux as a post-processing step: if the target is T1 Fire Res,
crafting T1 Cold Res + Blazing Flux might be cheaper if cold res has
higher weight in the pool.

**When this wins:** Desired resistance has lower weight than another
resistance in the pool, and flux orb is available/cheap.

---

### Strategy 10: Perfect Essence + Omen Crystallisation

Advanced combination. Use essence to guarantee one mod while keeping
existing mods on the other side.

```
Craft item with T1 prefix (e.g. via alt-regal) →
  Apply Dextral Crystallisation omen →
  Perfect Essence → rerolls all PREFIXES (keeps suffixes) + adds guaranteed mod

Result: guaranteed essence mod (prefix) + preserved suffix + random fill
```

**This is extremely powerful** for 3-mod crafting: lock one side via omen,
guarantee one mod via essence, and only the remaining 1-2 slots are random.

**When this wins:** Need 3+ targets, have an essence for one, and targets
are split across prefix/suffix.

---

## Part 2: Decision Conditions Catalog

Every condition the rule-list needs to evaluate, organized by category.

### Item State Conditions

```python
# Rarity — determines which currencies can be used
rarity_is(Normal)           # can: transmute, alchemy
rarity_is(Magic)            # can: augment, alteration, regal, annulment, greater_essence
rarity_is(Rare)             # can: chaos, exalted, annulment, divine, perfect_essence

# Mod counts — how full is the item?
mod_count_eq(n)             # exactly n mods (0-6)
mod_count_gte(n)            # n or more mods
mod_count_lte(n)            # n or fewer mods
open_prefix_gte(n)          # at least n open prefix slots (0-3)
open_suffix_gte(n)          # at least n open suffix slots (0-3)
```

### Target Progress Conditions

```python
# How close are we to the goal?
has_any_target()            # at least 1 target family present
has_target(family)          # specific target family present
all_targets_hit()           # ALL target families present (any tier)
all_targets_at_tier()       # ALL targets at required tier or better
targets_on_item_gte(n)      # n or more target families present
targets_on_item_eq(n)       # exactly n targets present
missing_target_prefix()     # at least 1 target prefix not yet present
missing_target_suffix()     # at least 1 target suffix not yet present

# Distinguishes "almost done" from "just started"
targets_remaining_lte(n)    # n or fewer targets still missing
```

### Junk/Risk Conditions

```python
# Should we annul? Is it safe?
has_non_target_removable()      # at least 1 non-fractured non-target mod exists
removable_gt_targets()          # count(removable junk) > count(targets on item)
                                # annul more likely hits junk than target

# Slot blockage — full slots with no targets
prefix_full_no_target_prefix()  # 3/3 prefixes used, none are targets → stuck
suffix_full_no_target_suffix()  # 3/3 suffixes used, none are targets → stuck

# Specific junk location (for omen decisions)
junk_prefix_exists()            # a non-target prefix exists
junk_suffix_exists()            # a non-target suffix exists
all_junk_is_prefix()            # all junk mods are prefixes (dextral annul safe)
all_junk_is_suffix()            # all junk mods are suffixes (sinistral annul safe)
targets_and_junk_same_side()    # targets + junk on same affix type (omen can't help)
```

### Budget/Progress Conditions

```python
# When to give up and restart
cost_spent_gte(threshold)       # total chaos spent >= threshold
cost_since_restart_gte(thresh)  # cost since last scour/buy >= threshold
step_count_gte(n)               # total simulation steps >= n
restart_count_gte(n)            # number of times we've restarted >= n
```

### Combinators

```python
AND(a, b)       # both true
OR(a, b)        # either true
NOT(a)          # negate
```

### Condition Notes

Some conditions that seem useful but should NOT be predicates:

- **Pool-specific conditions** ("target weight > 5% of pool"): these are
  static per optimization run, not per-step. They affect which SEED is best,
  not which rule fires. Pre-compute and use to select initial population bias.
- **"Last action was X"**: creates state dependency between steps, complicates
  the simulation. Rule-lists should be memoryless — decision based solely on
  current item state + budget.

---

## Part 3: Seed Rule-Lists

Each seed encodes a known strategy. Seeds are parameterized where noted —
the optimizer creates variants with different thresholds and currency tiers.

### Seed 1: Alt-Regal-Exalt (baseline)

The most common crafting approach. Fish for target on magic, transition to
rare, exalt fill.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)                 THEN augment
 4. IF rarity_is(Magic)                                      THEN regal
 5. IF all_targets_hit                                       THEN DONE
 6. IF cost_spent_gte(500)                                   THEN SCOUR
 7. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 8. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 9. IF has_non_target_removable AND removable_gt_targets     THEN annulment
10. DEFAULT                                                  THEN SCOUR
```

**Variants generated:** 3x currency tier (normal, greater, perfect) = 3 seeds.
Each variant replaces transmute/regal/exalted with their greater/perfect
equivalents. Total: seeds 1a, 1b, 1c.

---

### Seed 2: Skip-Augment Alt-Regal

Same as Seed 1 but skips augment. When target is hit on transmute with 1 mod,
regal directly (regal adds 1 mod regardless). Saves augment cost when the
other affix type's pool is all junk.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(500)                                   THEN SCOUR
 6. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 7. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 8. IF has_non_target_removable AND removable_gt_targets     THEN annulment
 9. DEFAULT                                                  THEN SCOUR
```

---

### Seed 3: Chaos Swap

Use chaos orb's remove-1-add-1 mechanic. Only viable when starting with no
targets (nothing to lose). Protected variant uses erasure omen.

```
 1. IF rarity_is(Normal)                                    THEN alchemy
 2. IF all_targets_hit                                       THEN DONE
 3. IF cost_spent_gte(2000)                                  THEN FAIL
 4. DEFAULT                                                  THEN chaos
```

**Protected variant (3b):** with Dextral Erasure omen when targets are prefixes:
```
 1. IF rarity_is(Normal)                                    THEN alchemy
 2. IF all_targets_hit                                       THEN DONE
 3. IF cost_spent_gte(2000)                                  THEN FAIL
 4. IF has_any_target AND junk_suffix_exists                 THEN chaos + dextral_erasure
 5. DEFAULT                                                  THEN chaos
```

---

### Seed 4: Omen-Targeted Exalts

Same early game as alt-regal, but uses sinistral/dextral exalt omens to
force the exalt into the correct affix type. More expensive per exalt but
dramatically higher hit rate.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)                 THEN augment
 4. IF rarity_is(Magic)                                      THEN regal
 5. IF all_targets_hit                                       THEN DONE
 6. IF cost_spent_gte(800)                                   THEN SCOUR
 7. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted + sinistral_exaltation
 8. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted + dextral_exaltation
 9. IF has_non_target_removable AND removable_gt_targets     THEN annulment
10. DEFAULT                                                  THEN SCOUR
```

---

### Seed 5: Omen Annul Recovery

Like seed 1 but with omen-protected annulment. When junk is all on one side
and targets on the other, use targeted annul for guaranteed safe removal.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)                 THEN augment
 4. IF rarity_is(Magic)                                      THEN regal
 5. IF all_targets_hit                                       THEN DONE
 6. IF cost_spent_gte(600)                                   THEN SCOUR
 7. IF junk_suffix_exists AND NOT junk_prefix_exists         THEN annulment + dextral_annulment
 8. IF junk_prefix_exists AND NOT junk_suffix_exists         THEN annulment + sinistral_annulment
 9. IF has_non_target_removable AND removable_gt_targets     THEN annulment
10. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
11. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
12. DEFAULT                                                  THEN SCOUR
```

---

### Seed 6: Alchemy Slam

Skip the careful transmute→regal path. Alchemy directly to rare with 4 mods.
Best for multiple common targets.

```
 1. IF rarity_is(Normal)                                    THEN alchemy
 2. IF all_targets_hit                                       THEN DONE
 3. IF cost_spent_gte(1000)                                  THEN SCOUR
 4. IF rarity_is(Rare) AND NOT has_any_target                THEN SCOUR
 5. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 6. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 7. IF has_non_target_removable AND removable_gt_targets     THEN annulment
 8. DEFAULT                                                  THEN SCOUR
```

**Variant (6b):** with sinistral/dextral alchemy omen:
```
 1. IF rarity_is(Normal)                                    THEN alchemy + sinistral_alchemy
 2. ...
```

---

### Seed 7: Buy-Magic Shortcut

Skip alt-spam by buying a magic item with the first target mod from trade.
Regal to rare, then exalt fill.

```
 1. IF rarity_is(Normal)                                    THEN BUY_MAGIC(first_target)
 2. IF rarity_is(Magic) AND has_any_target                   THEN regal
 3. IF all_targets_hit                                       THEN DONE
 4. IF cost_spent_gte(600)                                   THEN BUY_MAGIC(first_target)
 5. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 6. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 7. IF has_non_target_removable AND removable_gt_targets     THEN annulment
 8. DEFAULT                                                  THEN SCOUR
```

---

### Seed 8: Fractured Base Start

Buy a fractured base with the hardest target locked. Craft remaining slots.

```
 1. IF rarity_is(Normal)                                    THEN BUY_FRACTURED(hardest_target)
 2. IF all_targets_hit                                       THEN DONE
 3. IF cost_spent_gte(800)                                   THEN FAIL
 4. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 5. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 6. IF has_non_target_removable AND removable_gt_targets     THEN annulment
 7. DEFAULT                                                  THEN SCOUR
```

Note: BUY_FRACTURED starts item as Rare with 1 fractured mod. SCOUR resets
to Normal but KEEPS the fractured mod (it's permanent). So after scour,
the item is Normal with 1 fractured mod — it needs transmute→aug→regal
to get back to rare, but the fractured mod is preserved.

Actually — scouring a fractured item gives a Normal with the fractured mod
still present. The rule-list needs to handle this edge. The optimizer should
discover that after scour on fractured: transmute, then regal (the fractured
mod counts as 1 mod, so magic with fractured+1 = 2 mods, regal to rare).

---

### Seed 9: Aggressive Restart (fast-fail)

Low budget threshold. Give up and restart early rather than investing in
a bad item. Relies on getting lucky with a cheap transmute→regal→exalt
sequence.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(80)                                    THEN SCOUR
 6. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 7. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 8. DEFAULT                                                  THEN SCOUR
```

The low threshold (80c) means: if we haven't hit targets in ~80c of currency,
scour and try again. Bets on the average attempt being cheap enough that many
restarts are cheaper than one long attempt.

---

### Seed 10: Patient Salvager (annul-heavy)

High budget threshold, aggressive annulment. Commits to fixing the current
item rather than restarting. Good when base or progress is expensive.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)                 THEN augment
 4. IF rarity_is(Magic)                                      THEN regal
 5. IF all_targets_hit                                       THEN DONE
 6. IF cost_spent_gte(3000)                                  THEN FAIL
 7. IF prefix_full_no_target_prefix                          THEN annulment + sinistral_annulment
 8. IF suffix_full_no_target_suffix                          THEN annulment + dextral_annulment
 9. IF has_non_target_removable                              THEN annulment
10. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
11. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
12. DEFAULT                                                  THEN annulment
```

Note: rule 12 is a last resort — if nothing else matches, annul something
and hope it opens a useful slot. Risky but this strategy is about commitment.

---

### Seed 11: Escalating Currency Tiers

Start cheap, escalate to greater/perfect as the item gets closer to done.
Key insight: expensive currency is wasted early (when the item has 0 targets)
but valuable late (when you need to land the last target in a narrowed pool).

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(600)                                   THEN SCOUR
 6. IF targets_on_item_gte(2) AND open_prefix_gte(1) AND missing_target_prefix
                                                             THEN greater_exalted
 7. IF targets_on_item_gte(2) AND open_suffix_gte(1) AND missing_target_suffix
                                                             THEN greater_exalted
 8. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 9. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
10. IF has_non_target_removable AND removable_gt_targets     THEN annulment
11. DEFAULT                                                  THEN SCOUR
```

Rules 6-7 fire before 8-9: when 2+ targets are already hit (close to done),
use greater_exalted for better odds. When early (0-1 targets), use regular.
The specialize mutation can further refine these thresholds.

---

### Seed 12: Essence + Omen Crystallisation Combo

Advanced two-phase strategy. Build one side of the item first (e.g. suffixes),
then use essence + crystallisation omen to fill the other side while keeping
what you built.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(1000)                                  THEN SCOUR
 6. IF missing_target_suffix AND NOT missing_target_prefix   THEN essence(suffix_essence) + dextral_crystallisation
 7. IF missing_target_prefix AND NOT missing_target_suffix   THEN essence(prefix_essence) + sinistral_crystallisation
 8. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 9. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
10. IF has_non_target_removable AND removable_gt_targets     THEN annulment
11. DEFAULT                                                  THEN SCOUR
```

Rules 6-7 detect: "I have all my target prefixes but I'm missing target
suffixes" → use essence to guarantee a suffix while preserving existing
prefixes via crystallisation omen.

---

## Part 4: Seed Summary & Coverage Matrix

```
Seed  | Strategy               | Currency Tier | Uses Omens | Uses Trade | Restart Style
------|------------------------|---------------|------------|------------|---------------
1a    | Alt-Regal-Exalt        | Normal        | No         | No         | Scour @ 500c
1b    | Alt-Regal-Exalt        | Greater       | No         | No         | Scour @ 500c
1c    | Alt-Regal-Exalt        | Perfect       | No         | No         | Scour @ 500c
2     | Skip-Augment           | Normal        | No         | No         | Scour @ 500c
3a    | Chaos Swap             | Normal        | No         | No         | Fail @ 2000c
3b    | Chaos + Erasure Omen   | Normal        | Erasure    | No         | Fail @ 2000c
4     | Omen-Targeted Exalts   | Normal        | Exaltation | No         | Scour @ 800c
5     | Omen Annul Recovery    | Normal        | Annulment  | No         | Scour @ 600c
6a    | Alchemy Slam           | Normal        | No         | No         | Scour @ 1000c
6b    | Alchemy + Omen         | Normal        | Alchemy    | No         | Scour @ 1000c
7     | Buy-Magic Shortcut     | Normal        | No         | BUY_MAGIC  | Buy @ 600c
8     | Fractured Base Start   | Normal        | No         | BUY_FRAC   | Fail @ 800c
9     | Aggressive Restart     | Normal        | No         | No         | Scour @ 80c
10    | Patient Salvager       | Normal        | Annulment  | No         | Fail @ 3000c
11    | Escalating Tiers       | Mixed         | No         | No         | Scour @ 600c
12    | Essence + Crystallise  | Normal        | Crystal    | No         | Scour @ 1000c
```

Total: 16 seed rule-lists covering the full strategy space.
40% of 200 population = 80 seed slots → each seed duplicated ~5x with
randomized threshold values (cost_spent, restart budgets) for diversity.

---

## Part 5: What the Optimizer Should Discover

Strategies that NO seed encodes, but that crossover and mutation could find:

1. **Hybrid escalation**: transmute fishing with normal → greater_regal →
   perfect_exalted. Mixed tiers per step.

2. **Conditional restart type**: SCOUR when cheap progress, BUY_MAGIC when
   expensive progress. No seed mixes restart types.

3. **Phase-dependent omens**: use sinistral_exalt when 1 target prefix
   missing, but dextral_exalt when 1 target suffix missing. Requires
   the specialize mutation to split an exalt rule by which side is missing.

4. **Annul before regal**: transmute → hit target → annul the aug'd suffix
   (if junk) → regal without the junk suffix blocking the pool. Unusual
   but mathematically can be better.

5. **Optimal restart threshold**: the exact chaos value at which scouring
   and restarting is cheaper than continuing. This is pool-specific and
   the GA will evolve it through threshold mutations.

6. **Chaos + omen combos**: chaos + omen of whittling (deterministically
   removes lowest req_level mod = worst mod) + greater_chaos (replacement
   is high tier). No seed encodes this combination.

7. **Multi-restart strategies**: BUY_MAGIC at first restart, SCOUR at
   subsequent restarts (because you already have the base). The budget
   tracking enables this via cost_since_restart conditions.

---

## Part 6: Conditions NOT Included (and Why)

These were considered but excluded from the predicate vocabulary:

- **"Last action was X"**: creates hidden state. Rule-lists should be
  memoryless — decision based on observable item state only.

- **"Target weight > X% of pool"**: static per optimization run, not
  per-step. Affects seed selection, not rule firing.

- **"Item has mod from family X" (non-target)**: too specific. The predicates
  work in terms of target vs non-target, not individual families. Family-
  specific logic would bloat the condition space without helping generalize.

- **"Regal will add prefix with P > 60%"**: requires forward simulation.
  The rule-list evaluates current state, not predicted next state. The
  optimizer implicitly learns these probabilities through MC fitness.

- **"Price of currency X > Y"**: prices are fixed for the optimization run.
  They affect which SEED is best, not per-step decisions. The optimizer
  accounts for this through fitness evaluation.

---

## Part 7: New Mechanics from Research (July 2026)

Mechanics confirmed from mobalytics, maxroll, timesaver.gg, fextralife guides.
Several of these were not in our original design docs.

### Perfect Essence: Remove-1-Add-1 (NOT full reroll)

**Corrected mechanic:** Perfect Essence removes ONE random modifier from a Rare
item and adds ONE guaranteed modifier. It does NOT reroll all mods. This is
fundamentally different from what our simulator design assumed.

```
Perfect Essence on Rare item with [ModA, ModB, ModC, ModD]:
  1. Remove 1 random mod (e.g. ModC removed)
  2. Add guaranteed essence mod (EssenceMod added)
  Result: [ModA, ModB, ModD, EssenceMod]
```

**Slot-forcing mechanic:** If the essence mod is a suffix and all 3 suffix slots
are full, the removal is FORCED to target a suffix (to make room). This gives
deterministic control without an omen:
- Fill all suffixes with junk → Perfect Essence (suffix type) → guaranteed to
  remove a suffix, keeps all prefixes intact.

**Omen interaction:** Sinistral/Dextral Crystallisation explicitly controls which
affix TYPE is removed:
- Sinistral Crystallisation → removes only a prefix
- Dextral Crystallisation → removes only a suffix
This is MORE powerful than slot-forcing because it works even when slots
aren't full.

**Implication for optimizer:** Perfect Essence is NOT a reroll — it's a surgical
swap. This makes it viable as a mid-craft correction tool, not just a starting
action. New action for the rule-list vocabulary:

```python
perfect_essence(name)              # remove 1 random mod, add 1 guaranteed
perfect_essence(name) + sinistral_crystallisation  # remove prefix, add guaranteed
perfect_essence(name) + dextral_crystallisation    # remove suffix, add guaranteed
```

### Greater Essence: Magic → Rare (like Regal but guaranteed)

**Mechanic:** Greater Essence upgrades a Magic item to Rare, guaranteeing one
specific modifier plus random fill. Effectively a Regal Orb that lets you
choose one of the added mods.

```
Greater Essence on Magic item with [ModA]:
  1. Upgrade to Rare
  2. Add guaranteed essence mod
  3. Fill remaining slots randomly (total 4 mods typically)
  Result: [ModA, EssenceMod, Random1, Random2] (Rare)
```

**Implication for optimizer:** Greater Essence can REPLACE the regal step:
```
Transmute → alt-spam for target → Greater Essence (instead of regal)
```
This gives you the regal transition + a guaranteed mod in one step. New seed.

### Omen of Greater Exaltation: Double Exalt

**Mechanic:** Next Exalted Orb adds TWO modifiers instead of one. Requires 2
open affix slots. Stacks with sinistral/dextral exaltation AND with
greater/perfect exalt tiers.

```
Omen of Greater Exaltation + Perfect Exalted Orb:
  → adds 2 mods, both with min_mod_level 50 (high tier only)

Omen of Greater Exaltation + Omen of Dextral Exaltation + Exalted Orb:
  → adds 2 SUFFIX mods
```

**Implication for optimizer:** This is extremely powerful as a finishing move.
When item has 2 open slots and both need to be filled, greater exaltation
uses 1 exalt (+ omen cost) instead of 2 exalts. New action:

```python
exalted + greater_exaltation                    # add 2 random mods
exalted + greater_exaltation + sinistral_exaltation  # add 2 prefixes
exalted + greater_exaltation + dextral_exaltation    # add 2 suffixes
```

### Omen of Whittling: Deterministic Chaos Removal

**Mechanic:** Next Chaos Orb removes the mod with the LOWEST item level
requirement (not tier — item level). This is deterministic: you can inspect
which mod will be removed before using it.

**Key distinction:** "lowest item level" means the mod whose req_level value
is lowest — typically the worst/most common mod on the item. This is NOT the
same as lowest tier (T5 fire res req_level might be higher than T3 of a
niche mod).

**Implication for optimizer:** Whittling + Chaos is a surgical replace: remove
the worst mod (known), add a random new one. Much safer than regular chaos.
New action:

```python
chaos + whittling           # deterministic remove lowest req_level + random add
greater_chaos + whittling   # same, but add is min_lv 35
perfect_chaos + whittling   # same, but add is min_lv 50
```

### Omen of Homogenising Exaltation

**Mechanic:** Next Exalted Orb adds a modifier that matches the "type" of
existing mods. If item has attack mods, adds another attack mod. Pushes
a themed cluster.

**Implication for optimizer:** Niche but useful for builds wanting stacked
damage types. Lower priority — add as action but don't seed.

### Reforging Bench: 3-to-1 Recycling

**Mechanic:** Three items of the SAME base type AND rarity → one new
unidentified item of same base type and rarity with rerolled mods.

Rules:
- Must be identical base (3x Gold Ring, not Gold + Iron + Sapphire)
- Must be same rarity (all Magic or all Rare)
- Cannot be corrupted
- Output ilvl = LOWEST ilvl of the three inputs
- Output is unidentified (random mods from normal pool)

**Implication for optimizer:** Reforging is essentially a FREE crafting
attempt — you spend 3 failed items instead of currency. In an SSF context
this is critical. In trade context, if base items are cheap (~1c each),
reforging costs 3c for what is effectively an Alchemy Orb.

The optimizer should model reforging as an alternative to alchemy/scour
when the player has accumulated failed craft attempts:

```python
REFORGE                    # cost: 2 × base_white price (you already have 1)
                           # result: unidentified Rare of same base
                           # equivalent to: scour + alchemy, but paid in items not currency
```

However, reforging requires THREE items, which means tracking inventory.
For the optimizer v1, we can model it as a cost-equivalent action:
- REFORGE cost = 2 × base_white_price (you need 2 more copies of the base)
- Output = same as alchemy (random 4 mods on Rare)

This is a simplification — in practice, failed crafts accumulate naturally.
But for the optimizer's MC simulation, treating it as a fixed-cost alchemy
alternative is accurate enough.

### Limit: One Essence Mod Per Item (0.5.0+)

**Mechanic:** An item can only have ONE essence-crafted modifier at a time.
Using a second essence removes the first. This prevents essence stacking.

**Implication for simulator:** When applying essence to an item that already
has an essence mod, the old essence mod must be removed first (counted as
the "remove 1" step of Perfect Essence, or replaced entirely by Greater).

### SSF Crafting Flow (from mobalytics guide)

The recommended SSF crafting chain reveals an important strategy we didn't
have:

```
1. Transmute → get 1 affix
2. Augment → get 2nd affix
3. Greater Essence → upgrade to Rare with guaranteed 3rd mod
4. Exalt → 4th and 5th affix
5. Desecrate → 6th affix (Abyss bone)
```

This uses Greater Essence AS the regal step, guaranteeing one mod during
the transition. Step 5 uses desecration for the final slot, which we had
as a separate system but hadn't integrated into the main crafting flow.

New seed incorporating this:

### Seed 13: SSF Flow (Essence-Regal + Desecrate Finish)

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)                 THEN augment
 4. IF rarity_is(Magic) AND has_any_target                   THEN greater_essence(target_essence)
 5. IF all_targets_hit                                       THEN DONE
 6. IF cost_spent_gte(800)                                   THEN SCOUR
 7. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 8. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
 9. IF has_non_target_removable AND removable_gt_targets     THEN annulment
10. DEFAULT                                                  THEN SCOUR
```

Rule 4: instead of plain regal, use Greater Essence to guarantee a target
mod during the Magic → Rare transition.

### Seed 14: Perfect Essence Surgical Swap

Use Perfect Essence mid-craft to replace a junk mod with a guaranteed target.
Most powerful with crystallisation omen for safety.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(1000)                                  THEN SCOUR
 6. IF has_non_target_removable AND missing_target_prefix AND junk_prefix_exists
                                                             THEN perfect_essence(prefix_target) + sinistral_crystallisation
 7. IF has_non_target_removable AND missing_target_suffix AND junk_suffix_exists
                                                             THEN perfect_essence(suffix_target) + dextral_crystallisation
 8. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted
 9. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted
10. IF has_non_target_removable AND removable_gt_targets     THEN annulment
11. DEFAULT                                                  THEN SCOUR
```

Rules 6-7: when there's a junk prefix and we need a target prefix, use
Perfect Essence + Sinistral Crystallisation to surgically remove the junk
prefix and replace it with the guaranteed essence mod. Zero risk to suffixes.

### Seed 15: Double Exalt Finisher

Use Omen of Greater Exaltation to fill the last 2 slots in a single action.
Combined with sinistral/dextral for targeting.

```
 1. IF rarity_is(Normal)                                    THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target               THEN alteration
 3. IF rarity_is(Magic)                                      THEN regal
 4. IF all_targets_hit                                       THEN DONE
 5. IF cost_spent_gte(600)                                   THEN SCOUR
 6. IF open_prefix_gte(2) AND missing_target_prefix          THEN exalted + greater_exaltation + sinistral_exaltation
 7. IF open_suffix_gte(2) AND missing_target_suffix          THEN exalted + greater_exaltation + dextral_exaltation
 8. IF open_prefix_gte(1) AND missing_target_prefix          THEN exalted + sinistral_exaltation
 9. IF open_suffix_gte(1) AND missing_target_suffix          THEN exalted + dextral_exaltation
10. IF has_non_target_removable AND removable_gt_targets     THEN annulment
11. DEFAULT                                                  THEN SCOUR
```

Rules 6-7: when 2+ slots open on one side, use double exalt + targeting
omen. Rules 8-9: when only 1 slot, use regular targeted exalt.

### Seed 16: Chaos + Whittling (Controlled Swap)

Use whittling omen to deterministically remove worst mod, then chaos adds
a random replacement. Safer than regular chaos.

```
 1. IF rarity_is(Normal)                                    THEN alchemy
 2. IF all_targets_hit                                       THEN DONE
 3. IF cost_spent_gte(1500)                                  THEN SCOUR
 4. IF has_any_target AND has_non_target_removable           THEN chaos + whittling
 5. IF NOT has_any_target                                    THEN chaos
 6. DEFAULT                                                  THEN SCOUR
```

Rule 4: when we have targets we want to keep, use whittling to ensure the
worst (lowest req_level) mod is removed — typically junk, not our targets.
Rule 5: when no targets yet, regular chaos is fine (nothing to lose).

---

## Part 8: Updated Action Vocabulary

New actions from research (add to optimizer module card):

```python
# ── Essence actions (expanded) ──
greater_essence(name)                    # Magic → Rare, guaranteed mod + random fill
perfect_essence(name)                    # Rare: remove 1 random, add 1 guaranteed
perfect_essence(name) + sinistral_crystallisation  # remove prefix, add guaranteed
perfect_essence(name) + dextral_crystallisation    # remove suffix, add guaranteed

# ── Double exalt ──
exalted + greater_exaltation                         # add 2 mods
exalted + greater_exaltation + sinistral_exaltation  # add 2 prefixes
exalted + greater_exaltation + dextral_exaltation    # add 2 suffixes
# Also works with greater_exalted / perfect_exalted

# ── Chaos + whittling ──
chaos + whittling                        # deterministic remove lowest req_level + add
greater_chaos + whittling                # same, add is min_lv 35
perfect_chaos + whittling                # same, add is min_lv 50

# ── Homogenising exalt ──
exalted + homogenising_exaltation        # add mod matching existing type cluster

# ── Reforge (item-cost alternative to alchemy) ──
REFORGE                                  # cost: 2 × base_white price
                                         # equivalent to scour + alchemy
```

---

## Part 9: Updated Seed Summary

```
Seed  | Strategy                 | Currency Tier | Uses Omens       | Uses Trade | Restart
------|--------------------------|---------------|------------------|------------|--------
1a    | Alt-Regal-Exalt          | Normal        | No               | No         | Scour@500c
1b    | Alt-Regal-Exalt          | Greater       | No               | No         | Scour@500c
1c    | Alt-Regal-Exalt          | Perfect       | No               | No         | Scour@500c
2     | Skip-Augment             | Normal        | No               | No         | Scour@500c
3a    | Chaos Swap               | Normal        | No               | No         | Fail@2000c
3b    | Chaos + Erasure          | Normal        | Erasure          | No         | Fail@2000c
4     | Omen-Targeted Exalts     | Normal        | Exaltation       | No         | Scour@800c
5     | Omen Annul Recovery      | Normal        | Annulment        | No         | Scour@600c
6a    | Alchemy Slam             | Normal        | No               | No         | Scour@1000c
6b    | Alchemy + Omen           | Normal        | Alchemy          | No         | Scour@1000c
7     | Buy-Magic Shortcut       | Normal        | No               | BUY_MAGIC  | Buy@600c
8     | Fractured Base Start     | Normal        | No               | BUY_FRAC   | Fail@800c
9     | Aggressive Restart       | Normal        | No               | No         | Scour@80c
10    | Patient Salvager         | Normal        | Annulment        | No         | Fail@3000c
11    | Escalating Tiers         | Mixed         | No               | No         | Scour@600c
12    | Essence + Crystallise    | Normal        | Crystallisation  | No         | Scour@1000c
13    | SSF Flow (Ess-Regal)     | Normal        | No               | No         | Scour@800c
14    | Perf Essence Surgical    | Normal        | Crystallisation  | No         | Scour@1000c
15    | Double Exalt Finisher    | Normal        | Greater+Targeted | No         | Scour@600c
16    | Chaos + Whittling        | Normal        | Whittling        | No         | Scour@1500c
```

Total: 20 seed rule-lists. 40% of 200 population = 80 seed slots → 4x each.

---

## Part 10: Simulator Corrections Needed

Based on research, the following simulator mechanics need updating:

1. **Perfect Essence**: currently modeled as full reroll. Must change to
   remove-1-add-1 mechanic. Slot-forcing rule (full suffix slots → must
   remove suffix) needs implementation.

2. **Greater Essence**: must model as Magic → Rare transition with guaranteed
   mod + random fill. Currently might not distinguish from Perfect.

3. **Omen of Greater Exaltation**: new omen type. Must add to OMENS dict
   with `qty_override: 2` or similar mechanism.

4. **Omen of Whittling**: must add to OMENS dict with `del_target: "lowest_req_level"`
   (deterministic removal, not random).

5. **Omen of Homogenising Exaltation**: must add with tag-matching logic.

6. **One essence mod per item**: track whether item has an essence mod.
   Applying a second essence removes the first.

7. **Reforging**: add as alternative to alchemy in the action vocabulary.
   Cost model: 2 × base_white price.

Sources:
- [Maxroll Reforging Bench Guide](https://maxroll.gg/poe2/resources/reforging-bench-guide)
- [Timesaver Omens Guide](https://timesaver.gg/blog/poe2-omens-guide)
- [Timesaver Essence Guide](https://timesaver.gg/blog/poe2-essence-guide)
- [Fextralife Essences Wiki](https://pathofexile2.wiki.fextralife.com/Essences)
- [PoECurrency Patch 0.5 Crafting Meta](https://www.poecurrency.com/news/poe-2-patch-0-5-0-new-crafting-meta-how-to-guarantee-prefixes-with-essences-omens)
