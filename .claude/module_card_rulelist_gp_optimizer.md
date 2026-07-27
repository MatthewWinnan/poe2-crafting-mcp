# Module Card: Rule-List GP Crafting Optimizer

## Problem Statement

A player has a blank base item (e.g. Gold Gloves, ilvl 82) and wants specific
mods on it (e.g. T1 Energy Shield + T1 Life + T1 Fire Resistance). What is the
cheapest sequence of crafting currency to apply, accounting for the fact that
every step has random outcomes that change what the best next step is?

This is a **policy optimization** problem over a stochastic process. The output
isn't a fixed recipe — it's a decision tree the player (or MCP agent) follows
reactively: "I'm in state X, what do I do next?"

## Core Idea: Rule-List as Genome

Each individual in the population is an **ordered list of rules**. On every
simulation tick, the rules are evaluated top-to-bottom. The first rule whose
condition matches the current item state fires, and its action is applied.

```
RuleList (evaluated top-to-bottom, first match fires):
  1. IF rarity == Normal                          THEN perfect_transmute
  2. IF rarity == Magic AND NOT has_any_target     THEN alteration
  3. IF rarity == Magic AND mod_count == 1         THEN augment
  4. IF rarity == Magic AND has_any_target          THEN regal
  5. IF all_targets_hit                             THEN DONE
  6. IF cost_spent > 300                            THEN scour  (restart)
  7. IF open_prefix > 0 AND missing_target_prefix   THEN greater_exalted
  8. IF has_junk_removable AND removable > targets  THEN annulment
  9. IF open_suffix > 0 AND missing_target_suffix   THEN exalted
 10. DEFAULT                                        THEN scour  (restart)
```

This IS a decision tree — but encoded as a flat priority list. The ordering
encodes priority: rule 5 (all targets hit → DONE) fires before rule 7
(exalt more) because it appears earlier. Reordering rules changes behavior.

### Why Rule-Lists Over Trees

- **Readable output**: the evolved rule-list IS the crafting guide. An MCP agent
  or player can follow it directly as "if X then Y" instructions.
- **Natural crossover**: splice two rule lists at a cut point. No tree surgery.
- **Bounded bloat**: list length is capped (max 20 rules). No infinite growth.
- **Easy seeding**: Phase 3 heuristics translate directly into rule-lists.
- **Equivalent power**: any binary decision tree maps to a rule-list (priority
  order = depth-first left-branch traversal of the tree).

## Data Structures

### Condition Predicates

The vocabulary of things a rule can test about the current item state.
Each predicate is a function `(ItemState, CraftTarget) -> bool`.

```python
@dataclass
class Condition:
    predicate: str       # name from the vocabulary below
    argument: str | int  # predicate-specific parameter

# ── Rarity ──
rarity_is(r)                    # r in {Normal, Magic, Rare}

# ── Mod presence (relative to target set) ──
has_any_target()                # at least 1 target family is on item
has_target(family)              # specific target family is on item
all_targets_hit()               # ALL target families present (any tier)
all_targets_at_tier()           # ALL targets present at required tier or better
missing_target_prefix()         # a target prefix family is not yet on item
missing_target_suffix()         # a target suffix family is not yet on item
has_non_target_removable()      # non-fractured mod exists that is NOT a target
targets_on_item_gte(n)          # number of target families present >= n

# ── Slot counts ──
open_prefix_gte(n)              # open prefix slots >= n
open_suffix_gte(n)              # open suffix slots >= n
mod_count_gte(n)                # total mod count >= n
mod_count_lte(n)                # total mod count <= n

# ── Budget/progress ──
cost_spent_gte(threshold)       # cumulative chaos spent >= threshold
step_count_gte(n)               # simulation steps taken >= n

# ── Combinators ──
AND(a, b)                       # both conditions true
OR(a, b)                        # either condition true
NOT(a)                          # negate

# ── Special ──
removable_gt_targets()          # |removable non-target mods| > |target mods on item|
                                # (annul is more likely to hit junk than treasure)
prefix_full_no_target_prefix()  # all 3 prefix slots used, none are targets
suffix_full_no_target_suffix()  # all 3 suffix slots used, none are targets
```

### Actions

What a rule can tell the simulator to do. Each action has a known chaos cost
looked up from the pre-flight PriceCache (see below).

```python
@dataclass
class Action:
    currency: str        # key from CURRENCIES dict, or a meta-action
    omen: str = ""       # optional omen modifier

# ── Terminal actions ──
DONE                     # declare success, stop simulation
FAIL                     # abandon, stop simulation (budget exceeded)

# ── Restart actions (different costs, different starting points) ──
SCOUR                    # wipe to Normal, keep base (cost: scouring orb)
BUY_BASE                 # buy fresh white base (cost: base trade price)
BUY_MAGIC(family)        # buy Magic with target mod already on it
                         # (cost: trade price, skips alt-spam phase entirely)
BUY_FRACTURED(family)    # buy fractured base with target locked
                         # (cost: trade price, starts with 1 permanent target)
REFORGE                  # 3-to-1 recycling (cost: 2 x base_white price)
                         # equivalent to scour + alchemy, paid in items

# ── Currency actions (all variants) ──
transmute, greater_transmute, perfect_transmute
augment, greater_augment, perfect_augment
alteration
regal, greater_regal, perfect_regal
chaos, greater_chaos, perfect_chaos
exalted, greater_exalted, perfect_exalted
annulment
alchemy

# ── Omen-modified actions ──
exalted + sinistral_exaltation      # force prefix
exalted + dextral_exaltation        # force suffix
exalted + greater_exaltation        # add 2 mods (needs 2 open slots)
exalted + greater_exaltation + sinistral_exaltation  # add 2 prefixes
exalted + greater_exaltation + dextral_exaltation    # add 2 suffixes
exalted + homogenising_exaltation   # add mod matching existing type cluster
annulment + sinistral_annulment     # remove prefix only
annulment + dextral_annulment       # remove suffix only
regal + sinistral_coronation        # regal adds prefix
regal + dextral_coronation          # regal adds suffix
chaos + whittling                   # deterministic: remove lowest req_level mod + add
greater_chaos + whittling           # same, but add is min_lv 35
perfect_chaos + whittling           # same, but add is min_lv 50

# ── Essence actions ──
greater_essence(name)                # Magic -> Rare, guaranteed mod + random fill
                                     # replaces regal step with a guaranteed mod
perfect_essence(name)                # Rare: remove 1 random mod, add 1 guaranteed
                                     # NOT a full reroll — surgical swap
perfect_essence(name) + sinistral_crystallisation  # remove a prefix, add guaranteed
perfect_essence(name) + dextral_crystallisation    # remove a suffix, add guaranteed
# NOTE: only 1 essence mod per item (0.5.0+). Second essence removes first.
# NOTE: if essence mod is suffix and all suffix slots full, removal is FORCED
#        to target a suffix (slot-forcing). Same for prefix. Deterministic
#        without an omen when slots are strategically filled.
```

### Rule and RuleList

```python
@dataclass
class Rule:
    condition: Condition     # when does this rule fire?
    action: Action           # what currency to apply?
    label: str = ""          # human-readable description (auto-generated)

@dataclass
class RuleList:
    rules: list[Rule]        # ordered, first match fires
    max_rules: int = 20      # hard cap on list length
    max_steps: int = 500     # simulation timeout (prevent infinite loops)

    def evaluate(self, item: ItemState, target: CraftTarget) -> Action:
        """Return the action for the current item state."""
        for rule in self.rules:
            if rule.condition.evaluate(item, target):
                return rule.action
        return Action("FAIL")  # no rule matched — shouldn't happen with DEFAULT
```

### CraftTarget

What the user wants to achieve. The optimizer evolves rule-lists to reach this.

```python
@dataclass
class CraftTarget:
    families: dict[str, int]   # family_name -> max acceptable tier (1=T1 only, 3=T1-T3)
    # e.g. {"IncreasedLife": 1, "FireResistance": 2, "IncreasedEnergyShield": 1}
    # means: want T1 Life, T1-T2 Fire Res, T1 ES

    def is_satisfied(self, item: ItemState) -> bool:
        """Are all target mods present at acceptable tier?"""
        for family, max_tier in self.families.items():
            matching = [m for m in item.mods if m.family == family and m.tier <= max_tier]
            if not matching:
                return False
        return True
```

## Pre-flight Price Cache

Before the optimizer runs, a single pre-flight phase fetches and caches ALL
prices the simulation could ever need. The MC loop never touches the network.

```python
@dataclass
class PriceCache:
    # ── HOT: currency prices (from poe.ninja cache, zero network) ──
    # Already in SQLite from refresh_prices(). Covers ALL crafting currencies:
    # transmute, greater_transmute, perfect_transmute, augment, alteration,
    # regal, chaos, exalted, annulment, divine, alchemy, scouring,
    # and all Greater/Perfect variants. Also essences and omens.
    currency: dict[str, float]         # "chaos" -> 1.0, "exalted" -> 5.0, etc.
    omen: dict[str, float]             # "sinistral_exaltation" -> 15.0, etc.
    essence: dict[str, float]          # "Essence of Torment" -> 8.0, etc.

    # ── COLD: base item prices (from trade API, fetched once per optimization) ──
    # These are the ONLY network calls the pre-flight makes. ~10 calls total.
    # Cached for the entire optimization run (prices stable within a session).
    base_white: float                  # white Gold Gloves base price
    base_magic_with: dict[str, float]  # target family -> price for Magic w/ that mod
    base_fractured_with: dict[str, float]  # target family -> price for fractured base

    # ── Reference (for craft-vs-buy verdict) ──
    trade_finished: float              # price of finished item with ALL target mods
```

### Pre-flight Fetch

Two phases — hot cache (instant) and cold fetches (trade API):

```python
def preflight_prices(
    base_name: str,
    target: CraftTarget,
    league: str,
    trade_client: TradeClient,
    price_db: PriceDatabase,
) -> PriceCache:
    """
    Fetch all prices needed for optimization.

    Phase 1 (HOT — instant, from poe.ninja SQLite cache):
      All currency, essence, and omen prices. These are already cached
      from refresh_prices() and cover every crafting currency variant.
      Zero network calls.

    Phase 2 (COLD — ~10 trade API calls, cached for session):
      Base item prices at various states (white, magic+target, fractured).
      These require live trade search. Done once, never repeated during
      the 5M+ MC evaluations of the optimizer.
    """
    cache = PriceCache()

    # ── Phase 1: HOT (poe.ninja cache, instant) ──
    cache.currency = price_db.get_all_currency_rates()
    cache.omen = {name: price_db.get_item_price(name) for name in KNOWN_OMENS}
    cache.essence = {name: price_db.get_item_price(name) for name in KNOWN_ESSENCES}

    # ── Phase 2: COLD (trade API, ~10 calls) ──

    # Base item (white) — 1 trade call
    cache.base_white = trade_client.estimate_price(
        base_name, rarity="normal", league=league)

    # Magic with each target mod — 1 trade call per target family
    for family in target.families:
        stat_id = resolve_family_to_stat_id(family)
        cache.base_magic_with[family] = trade_client.estimate_price(
            base_name, rarity="magic", stat_filters=[stat_id], league=league)

    # Fractured with each target — 1 trade call per target family
    for family in target.families:
        stat_id = resolve_family_to_stat_id(family)
        cache.base_fractured_with[family] = trade_client.estimate_price(
            base_name, fractured=True, stat_filters=[stat_id], league=league)

    # Finished item — what does the end product cost on trade?
    all_stat_ids = [resolve_family_to_stat_id(f) for f in target.families]
    cache.trade_finished = trade_client.estimate_price(
        base_name, stat_filters=all_stat_ids, league=league)

    return cache
```

This means the restart actions have real costs:
- SCOUR: `cache.currency["scouring"]` (~0.5 chaos)
- BUY_BASE: `cache.base_white` (varies, often 1-10 chaos)
- BUY_MAGIC("IncreasedES"): `cache.base_magic_with["IncreasedES"]` (could be 30 chaos)
- BUY_FRACTURED("IncreasedES"): `cache.base_fractured_with["IncreasedES"]` (could be 200 chaos)

The GP can discover: "buying a Magic base with T1 ES for 30 chaos and skipping
100 expected alterations at 0.1 chaos each (10 chaos) is NOT worth it" — or
conversely, "buying a fractured T1 ES base for 80 chaos saves 300 chaos of
expected crafting" because it eliminates all risk on that mod.

Unavailable items get price `float('inf')` — the optimizer naturally avoids
actions with infinite cost.

## Genetic Programming Engine

### Population & Generations

```
Population size:      200 rule-lists
Generations:          50-100
Evaluation per ind:   500 Monte Carlo trials
Elitism:              top 10% carried forward unchanged
Tournament size:      3 (pick 3 random, winner = best Pareto rank)
Crossover rate:       70%
Mutation rate:        30% (of offspring, multiple mutation types)
```

### Fitness Evaluation

Each rule-list is evaluated by running it as the crafting policy for M=500
independent Monte Carlo simulations. Each simulation:

1. Start with a blank Normal item at target ilvl
2. Loop: evaluate rule-list -> get action -> apply action -> update cost
3. Stop when: DONE (success), FAIL (budget/abandon), or step_count > max_steps
4. Record: success/fail, total cost, step count

From 500 trials, compute:

```python
@dataclass
class Fitness:
    # ── Pareto objectives (3 dimensions — NSGA-II optimizes these) ──
    expected_cost: float        # mean(cost) across successful trials
    success_rate: float         # fraction of trials that hit DONE
    cost_p90: float             # 90th percentile cost (consistency/risk)
    # Minimized as: (expected_cost, 1 - success_rate, cost_p90)

    # ── Reported stats (for output, not Pareto dimensions) ──
    cost_median: float
    cost_std: float
    expected_steps: float       # mean(steps) across successful trials
    step_median: float

    # ── Parsimony (lexicographic tiebreaker within same Pareto rank) ──
    rule_count: int             # fewer rules = preferred at equal fitness

    # ── Hard constraints (violators killed before selection) ──
    # success_rate < 0.05       -> killed (degenerate)
    # all 500 trials timeout    -> killed (infinite loop)
```

### Pareto Objectives: Three

**Minimize: expected_cost** (cheap is good)
**Minimize: 1 - success_rate** (reliable is good)
**Minimize: cost_p90** (consistent is good — no nasty tail surprises)

Why three:
- expected_cost alone hides strategies that are cheap on average but
  occasionally explode to 10x (annul-rework loops with bad luck).
- success_rate alone doesn't distinguish "fails at 100 chaos" from
  "fails at 5000 chaos" — both are failures but one wasted much more.
- cost_p90 captures **consistency**: a strategy with 100c average and
  130c p90 is fundamentally better than 80c average with 400c p90,
  even though the second is "cheaper on average." Players want to know
  their worst realistic case, not just the average.

The 3D Pareto front is manageable because:
- We cluster into 3-5 strategy families anyway — each gets a summary line
- Families naturally separate along the front (cheap/risky vs expensive/safe)
- NSGA-II handles 3 objectives efficiently (well-studied, no degeneration)

Steps is NOT a Pareto objective — it correlates with cost (more steps = more
currency spent). Reported for interest but not optimized.

Rule-list size is a **parsimony tiebreaker**: within the same Pareto rank and
same crowding distance, prefer the shorter rule-list. This prevents bloat
without distorting the cost/success/consistency trade-off.

### NSGA-II Selection

Standard non-dominated sorting with crowding distance:

1. Combine parent + offspring populations (400 total)
2. Sort into Pareto fronts:
   - Front 0: non-dominated (no one better in ALL THREE objectives)
   - Front 1: dominated only by Front 0
   - Front 2: dominated by Fronts 0-1
   - etc.
3. Fill next generation (200) from front 0, then front 1, etc.
4. When a front partially fits, prefer individuals in sparse regions of the
   objective space (crowding distance). At equal crowding, prefer fewer rules
   (parsimony tiebreaker).

### Genetic Operators

#### Crossover: One-Point Splice

```
Parent A (8 rules):  [A1, A2, A3, A4, A5, A6, A7, A8]
Parent B (6 rules):  [B1, B2, B3, B4, B5, B6]

Cut point A: after rule 3
Cut point B: after rule 4

Child 1: [A1, A2, A3, B5, B6]          (3 from A + 2 from B)
Child 2: [B1, B2, B3, B4, A4, A5, A6, A7, A8]  (4 from B + 5 from A)
```

This combines the "early game" logic of one parent with the "late game" logic
of another. Natural for crafting: parent A might be great at getting to Rare
with a target mod, parent B might be great at filling remaining slots.

#### Crossover: Uniform Rule Swap

For each position, randomly pick the rule from parent A or B. Handles parents
of different lengths by padding with None (skip).

#### Mutation: Point (change one rule's internals) — 25% of mutations

```
Before: IF rarity == Magic AND has_any_target  THEN regal
After:  IF rarity == Magic AND has_any_target  THEN greater_regal
                                                    ^^^^^^^ mutated
```

Or mutate the condition:

```
Before: IF open_prefix_gte(1) AND missing_target_prefix  THEN exalted
After:  IF open_prefix_gte(2) AND missing_target_prefix  THEN exalted
                          ^ mutated threshold
```

#### Mutation: Insert Rule — 10% of mutations

Add a new randomly-generated rule at a random position. Increases list length
by 1 (up to max_rules cap of 20).

#### Mutation: Delete Rule — 10% of mutations

Remove a random rule (except DEFAULT). Decreases list length by 1 (minimum 3).

#### Mutation: Swap Priority — 15% of mutations

Swap the positions of two rules. Changes which one fires first.

```
Before: [... rule5: annulment, rule6: exalted ...]
After:  [... rule5: exalted, rule6: annulment ...]
```

This is a powerful mutation — moving a "scour restart" rule higher means the
strategy gives up earlier and restarts more aggressively. Moving it lower means
it commits harder to salvaging the current item.

#### Mutation: Add/Remove Omen — 10% of mutations

Toggle an omen on a currency action, or swap one omen for another.

```
Before: THEN exalted
After:  THEN exalted + sinistral_exaltation
```

#### Mutation: Specialize (split rule) — 10% of mutations

Fork a general rule into two more specific versions at adjacent priorities.

```
Before:
  7. IF open_prefix AND missing_target_prefix  THEN exalted

After:
  7. IF open_prefix AND missing_target_prefix AND targets_on_item_gte(2)  THEN greater_exalted
  8. IF open_prefix AND missing_target_prefix  THEN exalted
```

The more specific rule fires first when the item is close to completion (use
expensive currency when it matters most). The general rule catches the rest.
This is a key discovery mechanism for learning when to escalate currency tier.

#### Mutation: Generalize (broaden condition) — 5% of mutations

Remove one AND-clause from a compound condition. Makes a rule fire in more
situations.

```
Before: IF rarity_is(Magic) AND has_any_target AND mod_count_lte(1)  THEN regal
After:  IF rarity_is(Magic) AND has_any_target                        THEN regal
```

#### Mutation: Swap Restart Action — 5% of mutations

Change a restart action between SCOUR, BUY_BASE, BUY_MAGIC(family), and
BUY_FRACTURED(family). Explores whether paying more upfront for a better
starting point saves money overall.

```
Before: IF cost_spent_gte(200)  THEN SCOUR
After:  IF cost_spent_gte(200)  THEN BUY_MAGIC("IncreasedEnergyShield")
```

#### Mutation: Adaptive Threshold Nudge — 10% of mutations

Instead of random threshold changes, bias toward values observed in successful
simulations. During MC evaluation, record the cost_spent and step_count at
each decision point. Nudge thresholds toward the median observed value.

```
Observed: successful crafts typically spent 80-150 chaos before hitting target
Current rule: IF cost_spent_gte(500) THEN SCOUR
Nudged to:    IF cost_spent_gte(180) THEN SCOUR     (toward observed p75)
```

### Bloat Control

Rule-lists are naturally bounded (max 20 rules), but can still accumulate
dead or redundant rules. Three mechanisms keep lists lean:

#### 1. Hard Size Cap

Maximum 20 rules per list. Insert mutations rejected at cap. Minimum 3 rules.

#### 2. Dead Rule Pruning

During MC evaluation, track which rules actually fired across 500 trials.
After evaluation, any rule that fired 0 times is removed. Run once per
generation on the entire population.

This is free — we're already evaluating every individual. Just add a fire
counter per rule.

#### 3. Semantic Equivalence Pruning

Before selection, run every rule-list against a fixed "probe set" of 30-50
representative item states:

```python
PROBE_STATES = [
    ItemState(rarity="Normal"),                              # blank
    ItemState(rarity="Magic", mods=[target_prefix]),         # magic with target
    ItemState(rarity="Magic", mods=[junk_prefix]),           # magic without target
    ItemState(rarity="Rare", mods=[target_p, target_s, junk]),  # rare 2/3 targets
    ItemState(rarity="Rare", mods=[junk, junk, junk]),       # rare all junk
    ItemState(rarity="Rare", mods=[t1, t2, t3, junk, junk, junk]),  # full, mixed
    # ... ~30-50 states covering key decision points
]
```

Compute action vector: `actions = [rl.evaluate(state, target) for state in PROBE_STATES]`

If two rule-lists produce identical action vectors, they are semantically
equivalent. Keep only the shorter one. This prevents population bloat from
individuals that differ syntactically but behave identically.

### Initial Population Seeding (from Phase 3 Heuristics)

40% of generation 0 is hand-written rule-lists encoding known strategies.
60% is random (ensures exploration). Seeds:

**Seed 1: Alt-Regal-Exalt (conservative, cheap)**
```
 1. IF rarity_is(Normal)                              THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target         THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)           THEN augment
 4. IF rarity_is(Magic)                                THEN regal
 5. IF all_targets_hit                                 THEN DONE
 6. IF cost_spent_gte(500)                             THEN SCOUR
 7. IF open_prefix_gte(1) AND missing_target_prefix    THEN exalted
 8. IF open_suffix_gte(1) AND missing_target_suffix    THEN exalted
 9. IF has_non_target_removable AND removable_gt_targets  THEN annulment
10. DEFAULT                                            THEN SCOUR
```

**Seed 2: Greater Currency Variant**
Same structure as Seed 1 but with greater_transmute, greater_regal,
greater_exalted. Tests whether narrowed pools justify higher per-use cost.

**Seed 3: Perfect Currency Variant**
Same with perfect variants. Extremely narrow pools, very expensive per use.

**Seed 4: Chaos Spam (brute force)**
```
 1. IF rarity_is(Normal)                THEN alchemy
 2. IF all_targets_hit                  THEN DONE
 3. IF cost_spent_gte(2000)             THEN FAIL
 4. DEFAULT                             THEN chaos
```

**Seed 5: Omen-Targeted Exalts**
```
 1. IF rarity_is(Normal)                              THEN transmute
 2. IF rarity_is(Magic) AND NOT has_any_target         THEN alteration
 3. IF rarity_is(Magic) AND mod_count_lte(1)           THEN augment
 4. IF rarity_is(Magic)                                THEN regal
 5. IF all_targets_hit                                 THEN DONE
 6. IF cost_spent_gte(800)                             THEN SCOUR
 7. IF open_prefix_gte(1) AND missing_target_prefix    THEN exalted + sinistral_exaltation
 8. IF open_suffix_gte(1) AND missing_target_suffix    THEN exalted + dextral_exaltation
 9. IF has_non_target_removable AND removable_gt_targets  THEN annulment
10. DEFAULT                                            THEN SCOUR
```

**Seed 6: Skip-Augment**
Same as Seed 1 but removes the augment step — transmute hits target on Magic
with 1 mod, then regal directly. Saves augment cost when the other affix
type's pool is bad.

**Seed 7: Aggressive Annul-Exalt Cycling**
Lower cost threshold (2000+), higher removable tolerance. Commits to
salvaging items rather than restarting.

**Seed 8: Aggressive Scour Restart**
Low cost_spent threshold (50-100 chaos). Restarts frequently, hoping to hit
a lucky transmute→regal→exalt run quickly.

**Seed 9: Buy-Magic Shortcut**
```
 1. IF rarity_is(Normal)                              THEN BUY_MAGIC(first_target)
 2. IF rarity_is(Magic) AND has_target(first_target)   THEN regal
 3. IF all_targets_hit                                 THEN DONE
 4. IF cost_spent_gte(400)                             THEN BUY_MAGIC(first_target)
 5. IF open_prefix_gte(1) AND missing_target_prefix    THEN exalted
 6. IF open_suffix_gte(1) AND missing_target_suffix    THEN exalted
 7. IF has_non_target_removable AND removable_gt_targets  THEN annulment
 8. DEFAULT                                            THEN SCOUR
```

**Seed 10: Fractured Base Start**
```
 1. IF rarity_is(Normal)                              THEN BUY_FRACTURED(hardest_target)
 2. IF all_targets_hit                                 THEN DONE
 3. IF cost_spent_gte(600)                             THEN FAIL
 4. IF open_prefix_gte(1) AND missing_target_prefix    THEN exalted
 5. IF open_suffix_gte(1) AND missing_target_suffix    THEN exalted
 6. IF has_non_target_removable AND removable_gt_targets  THEN annulment
 7. DEFAULT                                            THEN SCOUR
```

## Simulation Loop

```python
def evaluate_rulelist(
    rulelist: RuleList,
    mod_pool: dict,          # from get_craftable_mods()
    target: CraftTarget,
    prices: PriceCache,      # pre-flight cached prices
    n_trials: int = 500,
) -> Fitness:

    costs, steps, successes = [], [], []
    fire_counts = [0] * len(rulelist.rules)  # for dead rule detection

    for trial in range(n_trials):
        item = ItemState(item_class, ilvl, rarity="Normal")
        cost = 0.0
        step = 0

        while step < rulelist.max_steps:
            action, rule_idx = rulelist.evaluate_with_index(item, target)
            fire_counts[rule_idx] += 1

            if action.currency == "DONE":
                successes.append(True)
                break
            if action.currency == "FAIL":
                successes.append(False)
                break

            # ── Restart actions ──
            if action.currency == "SCOUR":
                cost += prices.currency.get("scouring", 0.5)
                item = ItemState(item_class, ilvl, rarity="Normal")
                step += 1
                continue
            if action.currency == "BUY_BASE":
                cost += prices.base_white
                item = ItemState(item_class, ilvl, rarity="Normal")
                step += 1
                continue
            if action.currency.startswith("BUY_MAGIC"):
                family = action.argument
                cost += prices.base_magic_with.get(family, float('inf'))
                item = ItemState(item_class, ilvl, rarity="Magic")
                item.mods = [roll_specific_mod(family, mod_pool)]
                step += 1
                continue
            if action.currency.startswith("BUY_FRACTURED"):
                family = action.argument
                cost += prices.base_fractured_with.get(family, float('inf'))
                item = ItemState(item_class, ilvl, rarity="Rare")
                mod = roll_specific_mod(family, mod_pool)
                mod.fractured = True
                item.mods = [mod]
                step += 1
                continue

            # ── Normal currency application ──
            cost += prices.currency.get(action.currency, 1.0)
            if action.omen:
                cost += prices.omen.get(action.omen, 0)
            simulator.apply_currency_to(item, action, mod_pool)
            step += 1

            if target.is_satisfied(item):
                successes.append(True)
                break
        else:
            successes.append(False)  # timeout

        costs.append(cost)
        steps.append(step)

    successful_costs = [c for c, s in zip(costs, successes) if s]
    return Fitness(
        expected_cost=mean(successful_costs) if successful_costs else float('inf'),
        success_rate=sum(successes) / len(successes),
        cost_p90=percentile(successful_costs, 90) if successful_costs else float('inf'),
        expected_steps=mean(steps),
        cost_median=median(successful_costs) if successful_costs else float('inf'),
        cost_std=stdev(successful_costs) if len(successful_costs) > 1 else 0,
        step_median=median(steps),
        rule_count=len(rulelist.rules),
        _fire_counts=fire_counts,  # used by dead rule pruning
    )
```

## Output: Strategy Families

After the GA converges, the Pareto front contains 20-50 non-dominated
rule-lists. Many share a common "spine" with minor variations.

### Clustering

Compute pairwise distance between rule-lists using:

```
distance(A, B) = edit_distance(
    [(r.condition.predicate, r.action.currency) for r in A.rules],
    [(r.condition.predicate, r.action.currency) for r in B.rules],
)
```

Hierarchical clustering with merge threshold = 3 edits. Each cluster becomes
a "strategy family." Present the best (lowest expected cost) member of each
family as the representative.

### Output Format (for MCP agent / CLI)

```
Optimization Results: Gold Gloves (ilvl 82)
Target: T1 IncreasedEnergyShield + T1 IncreasedLife + T2 FireResistance

Trade price for equivalent: ~180 chaos
Pre-flight: white base 2c | Magic+ES 35c | Fractured+ES 220c

Strategy Family A: "Alt-Regal with Greater Exalts" (best cost)
  Expected cost: 85 chaos | Success: 92% | Steps: ~150 | p90: 210 chaos
  Craft-vs-buy verdict: CRAFT (saves ~95 chaos on average)
  Rules:
    1. Normal item              -> transmute
    2. Magic, no target yet     -> alteration
    3. Magic, 1 mod, has target -> regal (skip augment)
    4. All targets on item      -> DONE
    5. Spent > 400 chaos        -> scour and restart
    6. Open prefix, need prefix -> greater exalted
    7. Open suffix, need suffix -> exalted
    8. Junk mod removable       -> annulment
    9. Otherwise                -> scour and restart

Strategy Family B: "Omen Exalts" (lowest risk)
  Expected cost: 120 chaos | Success: 98% | Steps: ~80 | p90: 160 chaos
  Craft-vs-buy verdict: CRAFT (saves ~60 chaos, much lower variance)
  Rules:
    ... (same early game, uses sinistral/dextral omens on exalt step)

Strategy Family C: "Chaos Spam" (fewest steps, not recommended)
  Expected cost: 950 chaos | Success: 45% | Steps: ~12 | p90: 2400 chaos
  Craft-vs-buy verdict: BUY (crafting costs 5x trade price)
```

The MCP agent receives the winning rule-list and can follow it step-by-step,
reporting to the user: "Your item is Rare with T1 ES and a junk suffix.
Rule 8 says: annul the junk. If annul removes the ES (33% chance), rule 5
triggers a scour restart."

### Craft-vs-Buy Verdict

Automatic from pre-flight data:

```python
verdict = "CRAFT" if best_strategy.expected_cost < prices.trade_finished else "BUY"
savings = prices.trade_finished - best_strategy.expected_cost
risk_note = "" if best_strategy.cost_p90 < prices.trade_finished else
    f"WARNING: p90 cost ({best_strategy.cost_p90}c) exceeds trade price"
```

## File Layout

```
src/poe2_crafting_mcp/crafting/
  optimizer/
    __init__.py
    gene.py              # Rule, RuleList, Condition, Action dataclasses
    conditions.py        # Predicate implementations (all the IF checks)
    fitness.py           # Monte Carlo evaluation -> Fitness + dead rule pruning
    nsga2.py             # NSGA-II selection, Pareto ranking, crowding distance
    operators.py         # Crossover + mutation operators (10 types)
    seeds.py             # Phase 3 heuristic rule-lists (initial population)
    clustering.py        # Post-convergence strategy family grouping
    prices.py            # PriceCache + preflight_prices()
    runner.py            # Top-level: configure + run optimization + format output
```

## Performance Plan

### Phase 1: Pure Python Prototype
- Population 50, MC trials 100, generations 20
- 50 * 100 * 20 = 100k simulation runs, each ~200 steps = ~20M pool lookups
- Estimated: 30-60 seconds (acceptable for prototyping)
- Validates correctness of GP operators, fitness, NSGA-II

### Phase 2: Numpy Vectorization
- Batch all 500 MC trials for one rule-list as array operations
- Pre-encode mod pool as weight arrays, cumulative sums
- Vectorized weighted random: `np.searchsorted(cumsum, np.random.rand(500) * total)`
- Target: 200 pop x 500 MC x 50 gen in ~30 seconds

### Phase 3: Rust Inner Loop (PyO3)
- Move ItemState + apply_currency + evaluate_rulelist to Rust
- Pool data as fixed arrays passed once, simulations run in parallel (rayon)
- Target: full optimization in <5 seconds
- Rust toolchain already in Nix flake

## Convergence Detection

Track the **hypervolume indicator** of the Pareto front each generation.
Hypervolume = area dominated by the front relative to a reference point
(e.g. cost=10000, success=0). When hypervolume change < 0.1% for 5
consecutive generations, stop early. Saves compute when the front stabilizes
at generation 25 instead of running to 100.

## Resolved Design Decisions

### 1. Pareto objectives: exactly 3
expected_cost + success_rate + cost_p90. Consistency matters — a strategy
with 80c average but 400c p90 is worse than 100c average with 130c p90 for
most players. Steps correlates with cost so it's reported but not optimized.
Rule-list size is a parsimony tiebreaker, not an objective. Hard prune only
for degenerates (success < 5%, infinite loops).

### 2. Encoding: rule-list GP (not templates, not free-form trees)
Expressiveness of decision trees, interpretability of linear recipes,
natural bloat bounds. The evolved rule-list IS the crafting guide.

### 3. Restart cost: includes base item price via PriceCache
SCOUR costs a scouring orb. BUY_BASE costs the trade price. BUY_MAGIC and
BUY_FRACTURED cost what trade charges for those items. The GP can discover
when paying more upfront for a better starting point saves money overall.

### 4. Craft-vs-buy: automatic from pre-flight trade_finished price
Every strategy output includes expected_cost vs trade_finished, with
savings amount and risk warning if p90 exceeds trade price.

### 5. Bloat control: triple mechanism
Hard cap (20 rules) + dead rule pruning (fire count tracking) + semantic
equivalence pruning (probe state action vectors). No parsimony pressure
in the fitness function — just a lexicographic tiebreaker.

### 6. Price architecture: hot cache + cold pre-flight
Currency/essence/omen prices come from poe.ninja SQLite cache (instant,
zero network). Only base item trade lookups (~10 API calls) are fetched
at optimization start and cached for the entire run. The 5M+ MC
evaluations never touch the network.

## Open Questions (remaining)

1. **Essence support completeness**: we have essence prices and can model
   essence as an action, but the simulator needs to handle the "guarantee 1
   mod + fill rest randomly" mechanic correctly. Depends on Sprint 5a
   essence pool data being accurate.

2. **Multi-base optimization**: should the optimizer compare across base types?
   "Gold Gloves vs Occult Gloves for this mod set" — run optimization for each
   base and compare. Straightforward but doubles/triples compute time.

3. **Partial target satisfaction**: sometimes 2/3 target mods is "good enough."
   Could add a soft target mode where is_satisfied returns a score (0-1)
   instead of bool. Fitness becomes expected_cost_per_satisfaction_point.
   Defer to v2.

4. **Mid-craft entry**: optimizer assumes starting from blank. If the player
   already has an item with some mods, they want "what do I do from HERE?"
   Model as ItemState with pre-set mods. The rule-list still works — it just
   starts evaluating from a non-Normal state. Need a CLI/MCP input for this.
