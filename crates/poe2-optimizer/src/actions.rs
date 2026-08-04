/// Currency application logic.
///
/// IDs must match Python gene.py Currency/Omen enums exactly.

use rand::Rng;

use crate::item_state::ItemState;
use crate::pool::ModPool;

// Currency IDs
pub const DONE: u16 = 0;
pub const FAIL: u16 = 1;
pub const SCOUR: u16 = 2;
pub const BUY_BASE: u16 = 3;
pub const BUY_MAGIC: u16 = 4;
pub const BUY_FRACTURED: u16 = 5;
pub const REFORGE: u16 = 6;
pub const TRANSMUTE: u16 = 10;
pub const GREATER_TRANSMUTE: u16 = 11;
pub const PERFECT_TRANSMUTE: u16 = 12;
pub const ALTERATION: u16 = 13;
pub const AUGMENT: u16 = 14;
pub const GREATER_AUGMENT: u16 = 15;
pub const PERFECT_AUGMENT: u16 = 16;
pub const REGAL: u16 = 17;
pub const GREATER_REGAL: u16 = 18;
pub const PERFECT_REGAL: u16 = 19;
pub const EXALTED: u16 = 20;
pub const GREATER_EXALTED: u16 = 21;
pub const PERFECT_EXALTED: u16 = 22;
pub const ANNULMENT: u16 = 23;
pub const CHAOS: u16 = 24;
pub const GREATER_CHAOS: u16 = 25;
pub const PERFECT_CHAOS: u16 = 26;
pub const ALCHEMY: u16 = 27;
pub const FRACTURING: u16 = 30;
pub const ESSENCE_GREATER: u16 = 31;
pub const ESSENCE_PERFECT: u16 = 32;
pub const DIVINE: u16 = 33;
pub const VAAL: u16 = 34;
pub const DESECRATE: u16 = 35;
pub const REVEAL: u16 = 36;
pub const ESSENCE_LESSER: u16 = 38;
pub const ESSENCE_NORMAL: u16 = 39;

// Omen IDs
pub const NO_OMEN: u16 = 0;
pub const SINISTRAL_EXALTATION: u16 = 1;
pub const DEXTRAL_EXALTATION: u16 = 2;
pub const GREATER_EXALTATION: u16 = 3;
pub const SINISTRAL_ANNULMENT: u16 = 4;
pub const DEXTRAL_ANNULMENT: u16 = 5;
pub const SINISTRAL_CORONATION: u16 = 6;
pub const DEXTRAL_CORONATION: u16 = 7;
pub const WHITTLING: u16 = 8;
pub const LIGHT: u16 = 12;

/// Apply a crafting currency to the item state.
pub fn apply_currency(
    item: &mut ItemState,
    currency: u16,
    omen: u16,
    pool: &ModPool,
    rng: &mut impl Rng,
) {
    match currency {
        SCOUR | BUY_BASE | REFORGE => {
            let cost = item.cost_spent;
            let steps = item.step_count;
            *item = ItemState::blank();
            item.cost_spent = cost;
            item.step_count = steps;
        }

        BUY_MAGIC => {
            let cost = item.cost_spent;
            let steps = item.step_count;
            *item = ItemState::blank();
            item.cost_spent = cost;
            item.step_count = steps;
            item.rarity = 1;
            // Add first MISSING target mod (simulates buying magic with that mod)
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_specific_mod(item, fam, pool, rng);
            }
        }

        BUY_FRACTURED => {
            let cost = item.cost_spent;
            let steps = item.step_count;
            *item = ItemState::blank();
            item.cost_spent = cost;
            item.step_count = steps;
            item.rarity = 2;
            // Add first MISSING target mod as fractured
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_specific_mod(item, fam, pool, rng);
                // Fracture it
                if item.prefix_count > 0 {
                    item.fractured_mask |= 1;
                } else if item.suffix_count > 0 {
                    item.fractured_mask |= 0x08; // bit 3 for suffix 0
                }
            }
        }

        TRANSMUTE | GREATER_TRANSMUTE | PERFECT_TRANSMUTE => {
            // Only works on Normal items. Normal → Magic with 1-2 mods.
            if item.rarity != 0 {
                return;
            }
            item.rarity = 1;
            let min_lv = min_level_for_currency(currency);
            let n_mods = rng.gen_range(1u8..=2u8);
            for _ in 0..n_mods {
                add_random_mod(item, pool, min_lv, omen, rng);
            }
        }

        // ALTERATION: Does NOT exist in PoE2. ID 13 reserved but unused.

        AUGMENT | GREATER_AUGMENT | PERFECT_AUGMENT => {
            // Only works on Magic items
            if item.rarity != 1 {
                return;
            }
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, omen, rng);
        }

        REGAL | GREATER_REGAL | PERFECT_REGAL => {
            // Only works on Magic items → Rare
            if item.rarity != 1 {
                return;
            }
            item.rarity = 2;
            let min_lv = min_level_for_currency(currency);
            let effective_omen = match omen {
                SINISTRAL_CORONATION => SINISTRAL_EXALTATION,
                DEXTRAL_CORONATION => DEXTRAL_EXALTATION,
                _ => omen,
            };
            add_random_mod(item, pool, min_lv, effective_omen, rng);
        }

        EXALTED | GREATER_EXALTED | PERFECT_EXALTED => {
            // Only works on Rare items
            if item.rarity != 2 {
                return;
            }
            let min_lv = min_level_for_currency(currency);
            let qty = if omen == GREATER_EXALTATION { 2 } else { 1 };
            for _ in 0..qty {
                add_random_mod(item, pool, min_lv, omen, rng);
            }
        }

        ANNULMENT => {
            // Only works on Magic or Rare items
            if item.rarity == 0 {
                return;
            }
            if omen == LIGHT {
                // Omen of Light: remove the desecrated (abyss) mod only.
                // Abyss mods are always suffixes. Remove last non-fractured suffix
                // and clear the desecrated_ever flag so re-desecration is possible.
                if item.flags & 0x08 != 0 {
                    remove_last_nonfractured_suffix(item);
                    item.flags &= !0x08; // clear has_been_desecrated_ever
                }
            } else {
                remove_random_mod(item, omen, rng);
            }
        }

        CHAOS | GREATER_CHAOS | PERFECT_CHAOS => {
            // Only works on Rare items
            if item.rarity != 2 {
                return;
            }
            let min_lv = min_level_for_currency(currency);
            // Whittling omen: remove lowest-req mod (deterministic)
            if omen == WHITTLING {
                remove_lowest_req_mod(item);
            } else {
                remove_random_mod(item, NO_OMEN, rng);
            }
            add_random_mod(item, pool, min_lv, NO_OMEN, rng);
        }

        ALCHEMY => {
            // Only works on Normal items → Rare
            if item.rarity != 0 {
                return;
            }
            item.rarity = 2;
            clear_mods(item);
            let n_mods = rng.gen_range(4u8..=6u8);
            for _ in 0..n_mods {
                if item.mod_count() >= 6 {
                    break;
                }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
        }

        FRACTURING => {
            // Only works on Rare items
            if item.rarity != 2 {
                return;
            }
            // Lock a random non-fractured mod
            let total = item.mod_count();
            if total > 0 {
                let target = rng.gen_range(0..total);
                if target < item.prefix_count {
                    item.fractured_mask |= 1 << target;
                } else {
                    item.fractured_mask |= 1 << (target - item.prefix_count + 3);
                }
            }
        }

        ESSENCE_GREATER => {
            // Greater Essence: Magic → Rare, guaranteed mod at BEST tier from ESSENCE pool.
            if item.rarity != 1 || item.has_essence_mod() {
                return;
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, TierRank::Best);
            }
        }

        ESSENCE_LESSER => {
            // Lesser Essence: Magic → Rare, guaranteed mod at WORST tier from ESSENCE pool.
            if item.rarity != 1 || item.has_essence_mod() {
                return;
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, TierRank::Worst);
            }
        }

        ESSENCE_NORMAL => {
            // Normal Essence: Magic → Rare, guaranteed mod at MID tier from ESSENCE pool.
            if item.rarity != 1 || item.has_essence_mod() {
                return;
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, TierRank::Mid);
            }
        }

        ESSENCE_PERFECT => {
            // Perfect Essence: Remove one non-fractured mod; add first MISSING target.
            // Only works on Rare items that already HAVE an essence mod (swaps it).
            // In-game: "Use on a Rare Item to swap the Crafted Modifier"
            if item.rarity != 2 || !item.has_essence_mod() {
                return;
            }
            remove_random_mod(item, NO_OMEN, rng);
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_specific_mod(item, fam, pool, rng);
            }
            item.set_essence_mod(true);
        }

        DIVINE => {
            // Doesn't change families/tiers — just sets the divined flag
            item.set_divined(true);
        }

        VAAL => {
            // Terminal: no state change modeled (optimizer doesn't track corruption)
        }

        DESECRATE => {
            // Only Rare items can be desecrated
            if item.rarity != 2 {
                return;
            }
            // Only desecrate once per item (one desecrated mod maximum in 0.5)
            // Use bit 3 of flags as "has_been_desecrated_ever"
            if item.flags & 0x08 != 0 {
                return; // Already desecrated this item once
            }
            item.set_desecrated(true);
        }

        REVEAL => {
            // Well of Souls: reveal 3 options from the DESECRATED pool (small, ~14 mods).
            // Player picks the best one. P(specific target) ≈ 1-(13/14)^3 ≈ 20%.
            //
            // Simplified model: 20% chance of placing the target abyss mod directly,
            // 80% chance of placing a random suffix (non-target abyss mod).
            // This is more accurate than drawing from the full 80k-weight pool.

            // Must be in desecrated state to reveal (requires prior DESECRATE)
            if !item.is_desecrated() {
                return;
            }
            item.set_desecrated(false);
            item.flags |= 0x08; // mark has_been_desecrated_ever

            let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
            if item.suffix_count >= max_s {
                return; // no room
            }

            // Check if there's a suffix target we're missing
            let missing_suffix_target = pool.target_suffix_families.iter()
                .find(|&&fam| !item.has_family(fam))
                .copied();

            if let Some(target_fam) = missing_suffix_target {
                // ~20% chance to get the specific target from pick-from-3
                // (14 options, pick 3, roughly 1 - (13/14)^3)
                if rng.gen::<f32>() < 0.20 {
                    // Success: place the target at a random tier
                    add_specific_mod(item, target_fam, pool, rng);
                } else {
                    // Got a non-target abyss mod — place a random suffix
                    let blocked: Vec<u16> = (0..item.suffix_count as usize)
                        .map(|i| item.suffix_families[i])
                        .filter(|&f| f != 0)
                        .collect();
                    let rng_val = rng.gen::<u64>();
                    if let Some((fam, tier)) = pool.sample_suffix(&blocked, 0, rng_val) {
                        let idx = item.suffix_count as usize;
                        item.suffix_families[idx] = fam;
                        item.suffix_tiers[idx] = tier;
                        item.suffix_count += 1;
                    }
                }
            } else {
                // No suffix target missing — place any random suffix
                let blocked: Vec<u16> = (0..item.suffix_count as usize)
                    .map(|i| item.suffix_families[i])
                    .filter(|&f| f != 0)
                    .collect();
                let rng_val = rng.gen::<u64>();
                if let Some((fam, tier)) = pool.sample_suffix(&blocked, 0, rng_val) {
                    let idx = item.suffix_count as usize;
                    item.suffix_families[idx] = fam;
                    item.suffix_tiers[idx] = tier;
                    item.suffix_count += 1;
                }
            }
        }

        _ => {}
    }
}

fn min_level_for_currency(currency: u16) -> u8 {
    match currency {
        GREATER_TRANSMUTE | GREATER_AUGMENT | GREATER_REGAL
        | GREATER_EXALTED | GREATER_CHAOS => 35,
        PERFECT_TRANSMUTE | PERFECT_AUGMENT | PERFECT_REGAL
        | PERFECT_EXALTED | PERFECT_CHAOS => 50,
        _ => 0,
    }
}

fn add_random_mod(
    item: &mut ItemState,
    pool: &ModPool,
    min_req_level: u8,
    omen: u16,
    rng: &mut impl Rng,
) {
    let max_p = if item.rarity == 1 { 1 } else { pool.max_prefixes };
    let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
    let prefix_open = item.prefix_count < max_p;
    let suffix_open = item.suffix_count < max_s;

    if !prefix_open && !suffix_open {
        return;
    }

    let force_prefix = omen == SINISTRAL_EXALTATION;
    let force_suffix = omen == DEXTRAL_EXALTATION;

    // Collect blocked families
    let mut blocked = Vec::with_capacity(6);
    for i in 0..item.prefix_count as usize {
        if item.prefix_families[i] != 0 {
            blocked.push(item.prefix_families[i]);
        }
    }
    for i in 0..item.suffix_count as usize {
        if item.suffix_families[i] != 0 {
            blocked.push(item.suffix_families[i]);
        }
    }

    let rng_val = rng.gen::<u64>();

    if force_prefix && prefix_open {
        if let Some((family, tier)) = pool.sample_prefix(&blocked, min_req_level, rng_val) {
            let idx = item.prefix_count as usize;
            item.prefix_families[idx] = family;
            item.prefix_tiers[idx] = tier;
            item.prefix_count += 1;
        }
    } else if force_suffix && suffix_open {
        if let Some((family, tier)) = pool.sample_suffix(&blocked, min_req_level, rng_val) {
            let idx = item.suffix_count as usize;
            item.suffix_families[idx] = family;
            item.suffix_tiers[idx] = tier;
            item.suffix_count += 1;
        }
    } else {
        // Natural: pick prefix or suffix weighted by pool weight
        let do_prefix = if !prefix_open {
            false
        } else if !suffix_open {
            true
        } else {
            let total = pool.prefix_total_weight + pool.suffix_total_weight;
            if total == 0 { true } else { (rng_val % total) < pool.prefix_total_weight }
        };

        if do_prefix {
            if let Some((family, tier)) = pool.sample_prefix(&blocked, min_req_level, rng_val) {
                let idx = item.prefix_count as usize;
                item.prefix_families[idx] = family;
                item.prefix_tiers[idx] = tier;
                item.prefix_count += 1;
            }
        } else if let Some((family, tier)) = pool.sample_suffix(&blocked, min_req_level, rng_val) {
            let idx = item.suffix_count as usize;
            item.suffix_families[idx] = family;
            item.suffix_tiers[idx] = tier;
            item.suffix_count += 1;
        }
    }
}

/// Find the first target family that is NOT yet on the item.
/// This enables sequential crafting: buy target 0, essence target 1, exalt target 2.
fn find_first_missing_target(item: &ItemState, pool: &ModPool) -> Option<u16> {
    for &fam in pool.all_target_families.iter() {
        if !item.has_family(fam) {
            return Some(fam);
        }
    }
    // All targets already present — return first target anyway (for tier upgrade attempts)
    pool.all_target_families.first().copied()
}

/// Which tier rank to place for essence variants.
enum TierRank {
    Best,   // Greater Essence: lowest tier number = highest power
    Mid,    // Normal Essence: median tier
    Worst,  // Lesser Essence: highest tier number = lowest power
}

/// Place a mod from the specified family using the ESSENCE pool's tier data.
/// Falls back to normal pool if the family isn't in the essence pool.
fn add_essence_mod(item: &mut ItemState, family: u16, pool: &ModPool, rank: TierRank) {
    // Check if family exists in essence pool or normal pool
    let in_ess_prefix = pool.essence_prefix_families.contains(&family);
    let in_ess_suffix = pool.essence_suffix_families.contains(&family);
    let in_norm_prefix = pool.prefix_families.contains(&family);
    let in_norm_suffix = pool.suffix_families.contains(&family);

    if !in_ess_prefix && !in_ess_suffix && !in_norm_prefix && !in_norm_suffix {
        return; // Family not in any pool (e.g. desecrated-only mod)
    }

    // Determine prefix vs suffix
    let place_as_prefix = if in_ess_prefix || in_norm_prefix {
        pool.target_prefix_families.contains(&family)
    } else {
        false // only in suffix pools
    };

    let tier = if place_as_prefix {
        if in_ess_prefix {
            tier_by_rank(family, &pool.essence_prefix_families, &pool.essence_prefix_tiers, &rank)
        } else {
            tier_by_rank(family, &pool.prefix_families, &pool.prefix_tiers, &rank)
        }
    } else {
        if in_ess_suffix {
            tier_by_rank(family, &pool.essence_suffix_families, &pool.essence_suffix_tiers, &rank)
        } else {
            tier_by_rank(family, &pool.suffix_families, &pool.suffix_tiers, &rank)
        }
    };

    if place_as_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = family;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
    } else if !place_as_prefix && item.suffix_count < pool.max_suffixes {
        let idx = item.suffix_count as usize;
        item.suffix_families[idx] = family;
        item.suffix_tiers[idx] = tier;
        item.suffix_count += 1;
    }
}

/// Place a mod from the specified family at a tier determined by rank.
/// Only works if the family exists in the normal pool.
fn add_specific_mod_at_tier_rank(item: &mut ItemState, family: u16, pool: &ModPool, rank: TierRank) {
    let in_prefix = pool.prefix_families.contains(&family);
    let in_suffix = pool.suffix_families.contains(&family);

    if !in_prefix && !in_suffix {
        return; // Family not in normal pool
    }

    let place_as_prefix = if in_prefix && in_suffix {
        pool.target_prefix_families.contains(&family)
    } else {
        in_prefix
    };

    let tier = if place_as_prefix {
        tier_by_rank(family, &pool.prefix_families, &pool.prefix_tiers, &rank)
    } else {
        tier_by_rank(family, &pool.suffix_families, &pool.suffix_tiers, &rank)
    };

    if place_as_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = family;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
    } else if !place_as_prefix && item.suffix_count < pool.max_suffixes {
        let idx = item.suffix_count as usize;
        item.suffix_families[idx] = family;
        item.suffix_tiers[idx] = tier;
        item.suffix_count += 1;
    }
}

/// Pick a tier by rank (best/mid/worst) from all tiers available for a family.
fn tier_by_rank(family: u16, families: &[u16], tiers: &[u8], rank: &TierRank) -> u8 {
    let mut family_tiers: Vec<u8> = Vec::new();
    for i in 0..families.len() {
        if families[i] == family {
            family_tiers.push(tiers[i]);
        }
    }
    if family_tiers.is_empty() {
        return 1;
    }
    family_tiers.sort();
    family_tiers.dedup();
    match rank {
        TierRank::Best => family_tiers[0],                              // lowest number = best
        TierRank::Worst => *family_tiers.last().unwrap(),               // highest number = worst
        TierRank::Mid => family_tiers[family_tiers.len() / 2],         // median
    }
}

fn add_specific_mod(item: &mut ItemState, family: u16, pool: &ModPool, rng: &mut impl Rng) {
    // Place a mod from the specified family at a random tier (weighted).
    // Only works if the family actually exists in the normal pool.
    let is_prefix = pool.prefix_families.contains(&family);
    let is_suffix = pool.suffix_families.contains(&family);

    if !is_prefix && !is_suffix {
        return; // Family not in normal pool (e.g. desecrated-only mod)
    }

    // Prefer prefix if family is in prefix pool and target says prefix
    let place_as_prefix = if is_prefix && is_suffix {
        pool.target_prefix_families.contains(&family)
    } else {
        is_prefix
    };

    let tier = if place_as_prefix {
        pick_random_tier_for_family(family, &pool.prefix_families, &pool.prefix_tiers, &pool.prefix_weights, rng)
    } else {
        pick_random_tier_for_family(family, &pool.suffix_families, &pool.suffix_tiers, &pool.suffix_weights, rng)
    };

    if place_as_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = family;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
    } else if !place_as_prefix && item.suffix_count < pool.max_suffixes {
        let idx = item.suffix_count as usize;
        item.suffix_families[idx] = family;
        item.suffix_tiers[idx] = tier;
        item.suffix_count += 1;
    }
}

fn pick_random_tier_for_family(family: u16, families: &[u16], tiers: &[u8], weights: &[u32], rng: &mut impl Rng) -> u8 {
    let mut total_weight: u64 = 0;
    let mut family_entries: Vec<(u8, u32)> = Vec::new();
    for i in 0..families.len() {
        if families[i] == family {
            family_entries.push((tiers[i], weights[i]));
            total_weight += weights[i] as u64;
        }
    }
    if family_entries.is_empty() || total_weight == 0 {
        return 1;
    }
    // Weighted random selection
    let target = rng.gen::<u64>() % total_weight;
    let mut cumulative: u64 = 0;
    for (tier, weight) in &family_entries {
        cumulative += *weight as u64;
        if cumulative > target {
            return *tier;
        }
    }
    family_entries.last().map(|(t, _)| *t).unwrap_or(1)
}

fn remove_random_mod(item: &mut ItemState, omen: u16, rng: &mut impl Rng) {
    let force_prefix = omen == SINISTRAL_ANNULMENT;
    let force_suffix = omen == DEXTRAL_ANNULMENT;

    let mut removable: Vec<(bool, usize)> = Vec::new();

    if !force_suffix {
        for i in 0..item.prefix_count as usize {
            if (item.fractured_mask >> i) & 1 == 0 {
                removable.push((true, i));
            }
        }
    }
    if !force_prefix {
        for i in 0..item.suffix_count as usize {
            if (item.fractured_mask >> (i + 3)) & 1 == 0 {
                removable.push((false, i));
            }
        }
    }

    if removable.is_empty() {
        return;
    }

    let choice = rng.gen_range(0..removable.len());
    let (is_prefix, idx) = removable[choice];
    remove_mod_at(item, is_prefix, idx);
}

fn remove_lowest_req_mod(item: &mut ItemState) {
    // Whittling: remove mod with lowest req_level (we don't track req_level
    // in ItemState, so just remove the last non-fractured mod as approximation)
    let mut removable: Vec<(bool, usize)> = Vec::new();
    for i in 0..item.prefix_count as usize {
        if (item.fractured_mask >> i) & 1 == 0 {
            removable.push((true, i));
        }
    }
    for i in 0..item.suffix_count as usize {
        if (item.fractured_mask >> (i + 3)) & 1 == 0 {
            removable.push((false, i));
        }
    }
    if let Some(&(is_prefix, idx)) = removable.last() {
        remove_mod_at(item, is_prefix, idx);
    }
}

fn remove_last_nonfractured_suffix(item: &mut ItemState) {
    // Find last non-fractured suffix and remove it
    for i in (0..item.suffix_count as usize).rev() {
        if (item.fractured_mask >> (i + 3)) & 1 == 0 {
            remove_mod_at(item, false, i);
            return;
        }
    }
}

fn remove_mod_at(item: &mut ItemState, is_prefix: bool, idx: usize) {
    if is_prefix {
        for i in idx..2 {
            item.prefix_families[i] = item.prefix_families[i + 1];
            item.prefix_tiers[i] = item.prefix_tiers[i + 1];
        }
        item.prefix_families[2] = 0;
        item.prefix_tiers[2] = 0;
        item.prefix_count = item.prefix_count.saturating_sub(1);
    } else {
        for i in idx..2 {
            item.suffix_families[i] = item.suffix_families[i + 1];
            item.suffix_tiers[i] = item.suffix_tiers[i + 1];
        }
        item.suffix_families[2] = 0;
        item.suffix_tiers[2] = 0;
        item.suffix_count = item.suffix_count.saturating_sub(1);
    }
}

fn clear_mods(item: &mut ItemState) {
    if item.fractured_mask == 0 {
        item.prefix_count = 0;
        item.suffix_count = 0;
        item.prefix_families = [0; 3];
        item.suffix_families = [0; 3];
        item.prefix_tiers = [0; 3];
        item.suffix_tiers = [0; 3];
    } else {
        // Keep fractured mods, compact to front
        let mut new_pc = 0u8;
        for i in 0..item.prefix_count as usize {
            if (item.fractured_mask >> i) & 1 == 1 {
                item.prefix_families[new_pc as usize] = item.prefix_families[i];
                item.prefix_tiers[new_pc as usize] = item.prefix_tiers[i];
                new_pc += 1;
            }
        }
        for i in new_pc as usize..3 {
            item.prefix_families[i] = 0;
            item.prefix_tiers[i] = 0;
        }
        item.prefix_count = new_pc;

        let mut new_sc = 0u8;
        for i in 0..item.suffix_count as usize {
            if (item.fractured_mask >> (i + 3)) & 1 == 1 {
                item.suffix_families[new_sc as usize] = item.suffix_families[i];
                item.suffix_tiers[new_sc as usize] = item.suffix_tiers[i];
                new_sc += 1;
            }
        }
        for i in new_sc as usize..3 {
            item.suffix_families[i] = 0;
            item.suffix_tiers[i] = 0;
        }
        item.suffix_count = new_sc;
    }
    item.set_essence_mod(false);
    item.set_desecrated(false);
    item.set_divined(false);
}
