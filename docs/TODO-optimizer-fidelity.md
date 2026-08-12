# Optimizer Fidelity Gaps

Known gaps between the MC evaluator model and real PoE2 crafting.

## 1. buy_magic price assumes flat rate (DONE)

**Problem**: `BUY_MAGIC` uses a fixed price for "any magic base with target mod",
but rare mods (e.g. IncreaseSocketedGemLevel at 0.97% weight) cost far more on
trade than common ones (e.g. PhysicalDamage at 16.5%).

**Fix**: Three auto trade price lookups in `_lookup_trade_prices()`:
1. White base price (normal rarity, correct category + ilvl)
2. Magic item with each target mod (per-family pricing)
3. Finished rare item with all target mods (CRAFT vs BUY verdict)

All prices converted to chaos equivalent via `_trade_price_to_chaos()` using
poe.ninja exchange rates. Floors applied: base_white >= 0.5c, magic >= base+0.5c.

**Where**: `preflight.py` → `_lookup_trade_prices()`, `_build_chaos_rates()`,
`_trade_price_to_chaos()`, `_TRADE_CURRENCY_TO_DB`.


## 2. No-op actions still charge cost (DONE)
## 2b. Alloy destructive no-op (DONE)

**Problem**: The Rust MC evaluator charges currency+omen cost BEFORE calling
`apply_currency()`. If the action is a no-op (e.g. exalting a Magic item),
the cost is wasted but nothing happens. The GP learns to avoid these through
wasted cost, BUT if the rule is dead code (never fires in successful trials),
it stays in the strategy and misleads users who follow it manually.

**Impact**: Strategies can contain impossible actions like "exalt a Magic item"
that technically work in MC (dead code) but fail in the craft CLI simulator.

**Fix options**:
- (a) Move cost charging AFTER apply_currency, only if the action actually
  modified the item (compare item state before/after). Cleanest but requires
  tracking state change.
- (b) Add a `did_apply` return value to `apply_currency()` → only charge cost
  if true. Simple but changes the API.
- (c) Post-process final strategies to remove rules with 0 fire_on_success.
  Already done by prune_dead_rules during evolution, but may need a final
  pass on the output strategies.
- (d) Add rarity preconditions to condition evaluation: exalt conditions
  should implicitly require Rare, transmute should require Normal, etc.
  This prevents the rule from firing at all, eliminating the no-op.

**Implemented**: (d) — `action_is_valid()` in `actions.rs` checks rarity/state
preconditions. `evaluate.rs` calls it after condition match but before firing:
if invalid, `continue` to next rule (no cost charged, no fire counted).

**Where**: `actions.rs` `action_is_valid()`, `evaluate.rs` line ~97.

**2b**: Alloy was removing a random mod BEFORE checking if the target exists
in the alloy pool. If the target isn't available as an alloy, the mod removal
is destructive for nothing. Fixed: check `alloy_{prefix,suffix}_families`
BEFORE calling `remove_random_mod`.

## 2c. Setup rules interfere with desecrated phases (DONE)

**Problem**: `build_setup_rules()` adds `missing_target_suffix → exalted` to
recreate prior-phase mods. But `missing_target_suffix` also matches the current
phase's desecrated target. Exalt can't place desecrated mods, so the rule fires
infinitely (250k times), blocking desecrate+reveal rules from ever executing.

**Fix**: Phases with `initial_state` (phase > 0) no longer get setup rules.
SCOUR resets to `initial_state` which already contains prior-phase mods, making
setup rules redundant. Applied in both `optimize_cooperative` and
`optimize_multi_target`.

## 2d. Desecrate/reveal had no price (DONE)

**Problem**: `desecrate` and `reveal` currencies had no entry in `_DEFAULTS`,
so Rust saw them as 0c cost. GP spammed desecrate+reveal for free.

**Fix**: Added `desecrate` price (median of cheapest bones from abyss category
in DB, ~0.01c) and `reveal` price (0c, free — just picking from options).


## 2e. Dead rules visible in final strategy output (DONE)

**Problem**: GP evolves dead-code rules (e.g. alloy on Magic items, essence_greater
on Rare items) that never fire due to `action_is_valid()` gating but still appear
in the final strategy output, confusing users. `prune_dead_rules` during evolution
has a minimum of 3 rules, so dead rules survive in small strategies.

**Fix**: Added a final pruning pass in `_label_strategy()` (runner.py) that removes
all dead rules (fire_on_success=0, fire_on_failure=0) with minimum 1 rule (not 3).
Runs right before building the user-facing strategy display.

## 2f. ESSENCE_PERFECT placed from normal pool (DONE — CRITICAL)

**Problem**: `ESSENCE_PERFECT` in `actions.rs` called `add_specific_mod()` which
places mods from the NORMAL pool. This let the GP treat essence_perfect as a
targeted mod-placement engine: remove any mod → place any target from normal pool.
The GP evolved "essence_greater + essence_perfect spam" strategies that guaranteed
any target at ~80c — far cheaper than realistic crafting.

**Impact**: Massive cost underestimation. Strategies like "use essence_perfect to
get PhysicalDamage on Gloves" showed 100% success when PhysicalDamage isn't even
in the essence pool for Gloves.

**Fix**: Changed `ESSENCE_PERFECT` to call `add_essence_mod()` + `add_random_essence_mod()`
(essence pool only), matching real PoE2 behavior where perfect essence swaps the
essence mod for another random one from the same pool.

**Where**: `actions.rs` ESSENCE_PERFECT handler, line ~383.

## 2g. Trade price currency conversion (DONE)

**Problem**: `_lookup_trade_prices()` used `median_price.amount` directly as chaos
value, but trade API returns prices in the listing's dominant currency (e.g.
"1 transmute" = 0.006c, not 1c). White bases showed "0.0c" and magic items showed
"1.0c" regardless of actual value.

**Fix**: Added `_TRADE_CURRENCY_TO_DB` mapping (trade API slugs → DB names),
`_build_chaos_rates()` (looks up chaos values from prices table), and
`_trade_price_to_chaos()` converter. All three trade lookups now convert properly.
Also added price floors: base_white >= 0.5c, magic >= base_white + 0.5c.

**Where**: `preflight.py` — `_trade_price_to_chaos()`, `_build_chaos_rates()`,
`_lookup_trade_prices()`.

## 3. Regal step missing in GP strategies (LOW — mitigated by #2 fix)

**Problem**: GP can evolve strategies that go transmute → exalt without a
regal step in between. With action validity gating (#2), exalt on Magic is
now skipped (not fired), so the GP learns it's dead code faster.

**Remaining impact**: Strategies may still omit an explicit regal rule if they
rely on buy_magic → (already rare via other path). Users reading the strategy
might not realize regal is needed. Mostly cosmetic now.

**Fix**: Ensure phase seeds always include `rarity_is(MAGIC) → REGAL` between
transmute-family and exalt-family rules. The GP can evolve around it but
starts with a valid baseline.

**Where**: `seeds.py` phase seeds, `decompose.py` build_setup_rules().
