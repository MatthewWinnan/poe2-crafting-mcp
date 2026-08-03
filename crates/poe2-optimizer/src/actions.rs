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
pub const ESSENCE_UPGRADE: u16 = 31;
pub const ESSENCE_SWAP: u16 = 32;
pub const DIVINE: u16 = 33;
pub const VAAL: u16 = 34;
pub const DESECRATE: u16 = 35;
pub const REVEAL: u16 = 36;

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
            item.rarity = 1;
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, omen, rng);
        }

        ALTERATION => {
            // Reroll magic: clear non-fractured + add 1
            clear_mods(item);
            add_random_mod(item, pool, 0, NO_OMEN, rng);
        }

        AUGMENT | GREATER_AUGMENT | PERFECT_AUGMENT => {
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, omen, rng);
        }

        REGAL | GREATER_REGAL | PERFECT_REGAL => {
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
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, omen, rng);
        }

        ANNULMENT => {
            remove_random_mod(item, omen, rng);
        }

        CHAOS | GREATER_CHAOS | PERFECT_CHAOS => {
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

        ESSENCE_UPGRADE => {
            // Magic → Rare + guaranteed target mod + fill
            // Only works if item doesn't already have an essence mod (one per item!)
            if item.has_essence_mod() {
                return; // Already has crafted mod — can't apply another
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            if let Some(fam) = find_first_missing_target(item, pool) {
                add_specific_mod(item, fam, pool, rng);
            }
            // Fill remaining (3-5 more mods)
            let fill = rng.gen_range(3u8..=5u8);
            for _ in 0..fill {
                if item.mod_count() >= 6 {
                    break;
                }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
        }

        ESSENCE_SWAP => {
            // Remove one non-fractured, non-essence mod; add first MISSING target
            // Only works if item doesn't already have an essence mod
            if item.has_essence_mod() {
                return; // Already has crafted mod
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
            item.set_desecrated(true);
        }

        REVEAL => {
            // Well of Souls: reveal 3 options, player picks the best one.
            // Model: roll 3 random mods from pool, if any is a target family
            // at acceptable tier, place it. Otherwise place the first one.
            item.set_desecrated(false); // consumed

            let max_p = if item.rarity == 1 { 1 } else { pool.max_prefixes };
            let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
            let prefix_open = item.prefix_count < max_p;
            let suffix_open = item.suffix_count < max_s;

            if !prefix_open && !suffix_open {
                return;
            }

            // Collect blocked families
            let mut blocked = Vec::with_capacity(6);
            for i in 0..item.prefix_count as usize {
                if item.prefix_families[i] != 0 { blocked.push(item.prefix_families[i]); }
            }
            for i in 0..item.suffix_count as usize {
                if item.suffix_families[i] != 0 { blocked.push(item.suffix_families[i]); }
            }

            // Roll 3 options (suffix-biased since most desecrated mods are suffixes)
            let mut best_option: Option<(u16, u8, bool)> = None; // (family, tier, is_prefix)
            for _ in 0..3 {
                let rng_val = rng.gen::<u64>();
                // Try suffix first (desecrated pool is mostly suffixes)
                if suffix_open {
                    if let Some((fam, tier)) = pool.sample_suffix(&blocked, 0, rng_val) {
                        // Prefer target families
                        if pool.all_target_families.contains(&fam) {
                            // Check tier acceptability
                            let is_acceptable = pool.target_max_tiers.iter()
                                .zip(pool.all_target_families.iter())
                                .any(|(max_t, tf)| *tf == fam && tier <= *max_t);
                            if is_acceptable {
                                best_option = Some((fam, tier, false));
                                break; // Found a target — take it immediately
                            }
                        }
                        if best_option.is_none() {
                            best_option = Some((fam, tier, false));
                        }
                    }
                } else if prefix_open {
                    if let Some((fam, tier)) = pool.sample_prefix(&blocked, 0, rng_val) {
                        if pool.all_target_families.contains(&fam) {
                            best_option = Some((fam, tier, true));
                            break;
                        }
                        if best_option.is_none() {
                            best_option = Some((fam, tier, true));
                        }
                    }
                }
            }

            // Place the best option found
            if let Some((family, tier, is_prefix)) = best_option {
                if is_prefix && prefix_open {
                    let idx = item.prefix_count as usize;
                    item.prefix_families[idx] = family;
                    item.prefix_tiers[idx] = tier;
                    item.prefix_count += 1;
                } else if !is_prefix && suffix_open {
                    let idx = item.suffix_count as usize;
                    item.suffix_families[idx] = family;
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

fn add_specific_mod(item: &mut ItemState, family: u16, pool: &ModPool, rng: &mut impl Rng) {
    // Place a mod from the specified family at a random tier (weighted)
    let is_prefix = pool.target_prefix_families.contains(&family);

    let tier = if is_prefix {
        pick_random_tier_for_family(family, &pool.prefix_families, &pool.prefix_tiers, &pool.prefix_weights, rng)
    } else {
        pick_random_tier_for_family(family, &pool.suffix_families, &pool.suffix_tiers, &pool.suffix_weights, rng)
    };

    if is_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = family;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
    } else if item.suffix_count < pool.max_suffixes {
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
