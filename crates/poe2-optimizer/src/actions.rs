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
pub const ABYSSAL_ECHOES: u16 = 9;
pub const SINISTRAL_NECROMANCY: u16 = 10;
pub const DEXTRAL_NECROMANCY: u16 = 11;
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
        SCOUR | BUY_BASE => {
            let cost = item.cost_spent;
            let steps = item.step_count;
            *item = ItemState::blank();
            item.cost_spent = cost;
            item.step_count = steps;
        }

        REFORGE => {
            // 3-to-1 bench: current + 2 spares → fresh Rare with 4 random mods.
            // Keeps fractured mods (if any), clears everything else.
            let cost = item.cost_spent;
            let steps = item.step_count;
            let frac = item.fractured_mask;
            *item = ItemState::blank();
            item.cost_spent = cost;
            item.step_count = steps;
            item.fractured_mask = frac;
            item.rarity = 2; // Rare
            // Restore fractured mods if any
            if frac != 0 {
                // Re-clear but preserve fracture data via clear_mods logic
                // (blank already has 0 mods, fractured_mask set above is enough)
            }
            // Fill with 4 random mods (like alchemy but always exactly 4)
            for _ in 0..4 {
                if item.mod_count() >= 6 {
                    break;
                }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
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
            let rank = TierRank::Best;
            // Try to place first missing target IF it's in the essence pool
            let placed = if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, rank)
            } else {
                false
            };
            // If target not in essence pool, place a random essence mod
            if !placed {
                add_random_essence_mod(item, pool, &rank, rng);
            }
            // Fill remaining slots with random normal mods (4-6 total for Rare)
            let n_fill = rng.gen_range(3u8..=5u8); // 1 essence + 3-5 random = 4-6 total
            for _ in 0..n_fill {
                if item.mod_count() >= 6 { break; }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
        }

        ESSENCE_LESSER => {
            // Lesser Essence: Magic → Rare, guaranteed mod at WORST tier from ESSENCE pool.
            if item.rarity != 1 || item.has_essence_mod() {
                return;
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            let rank = TierRank::Worst;
            let placed = if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, rank)
            } else {
                false
            };
            if !placed {
                add_random_essence_mod(item, pool, &rank, rng);
            }
            let n_fill = rng.gen_range(3u8..=5u8);
            for _ in 0..n_fill {
                if item.mod_count() >= 6 { break; }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
        }

        ESSENCE_NORMAL => {
            // Normal Essence: Magic → Rare, guaranteed mod at MID tier from ESSENCE pool.
            if item.rarity != 1 || item.has_essence_mod() {
                return;
            }
            item.rarity = 2;
            item.set_essence_mod(true);
            let rank = TierRank::Mid;
            let placed = if let Some(fam) = find_first_missing_target(item, pool) {
                add_essence_mod(item, fam, pool, rank)
            } else {
                false
            };
            if !placed {
                add_random_essence_mod(item, pool, &rank, rng);
            }
            let n_fill = rng.gen_range(3u8..=5u8);
            for _ in 0..n_fill {
                if item.mod_count() >= 6 { break; }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
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
            // Can't desecrate if already in desecrated state (pending reveal)
            if item.is_desecrated() {
                return;
            }
            item.set_desecrated(true);
            // Store omen consumed at bone application (affects later reveal)
            let stored = match omen {
                SINISTRAL_NECROMANCY => 1,
                DEXTRAL_NECROMANCY => 2,
                ABYSSAL_ECHOES => 3,
                _ => 0,
            };
            item.set_desecrate_omen(stored);
        }

        REVEAL => {
            // Well of Souls reveal: draw 3 options from the desecrated pool,
            // player picks best. Omens are consumed at bone (DESECRATE) step
            // and stored in item state — read them here.
            //
            // Affix type determination (matches real game):
            //  - Necromancy omen forces prefix (sinistral) or suffix (dextral)
            //  - All prefixes full + suffix open → suffix (guaranteed)
            //  - All suffixes full + prefix open → prefix (guaranteed)
            //  - Both open → random 50/50
            //  - Neither open → no room, skip

            if !item.is_desecrated() {
                return;
            }
            // Read omen stored at desecrate step, then clear
            let stored_omen = item.desecrate_omen();
            item.set_desecrated(false);
            item.set_desecrate_omen(0);
            item.flags |= 0x08; // mark has_been_desecrated_ever

            // Determine affix type (prefix vs suffix) for the reveal
            let max_p = pool.max_prefixes;
            let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
            let prefix_open = item.prefix_count < max_p;
            let suffix_open = item.suffix_count < max_s;

            let is_prefix = if stored_omen == 1 { // SINISTRAL_NECROMANCY
                true  // force prefix
            } else if stored_omen == 2 { // DEXTRAL_NECROMANCY
                false // force suffix
            } else if prefix_open && !suffix_open {
                true  // only prefix slots available
            } else if suffix_open && !prefix_open {
                false // only suffix slots available
            } else if prefix_open && suffix_open {
                rng.gen::<bool>() // both open → 50/50
            } else {
                return; // neither open — no room
            };

            // Validate the chosen affix type has room
            if is_prefix && !prefix_open {
                return;
            }
            if !is_prefix && !suffix_open {
                return;
            }

            // Find missing desecrated target for this affix type
            let target_fam = if is_prefix {
                pool.target_prefix_families.iter()
                    .find(|&&fam| !item.has_family(fam) && !pool.prefix_families.contains(&fam))
                    .copied()
            } else {
                pool.target_suffix_families.iter()
                    .find(|&&fam| !item.has_family(fam) && !pool.suffix_families.contains(&fam))
                    .copied()
            };

            // Get pool size for hit probability calculation
            let pool_size = if is_prefix {
                pool.desecrated_prefix_pool_size as u32
            } else {
                pool.desecrated_suffix_pool_size as u32
            };

            if let Some(fam) = target_fam {
                // Calculate P(hit) = 1 - C(pool-1, 3) / C(pool, 3)
                // Simplified: P(hit) = 1 - (pool-1)(pool-2)(pool-3) / (pool)(pool-1)(pool-2)
                //           = 1 - (pool-3)/pool = 3/pool  (for target_count=1)
                let p_hit = if pool_size <= 3 {
                    1.0_f32
                } else {
                    // P(miss) = C(pool-1, 3) / C(pool, 3) = (pool-3)/pool * ...
                    // Full: P(miss) = (pool-1)*(pool-2)*(pool-3) / (pool*(pool-1)*(pool-2))
                    //              = (pool-3)/pool
                    // Wait, that's only for target_count=1. More precisely:
                    // P(miss) = C(pool - target_count, draws) / C(pool, draws)
                    // With target_count=1, draws=3:
                    // = C(pool-1, 3) / C(pool, 3) = (pool-3)/pool * (pool-2)/(pool-1) ...
                    // Actually simplest: (pool-1)(pool-2)(pool-3) / (pool(pool-1)(pool-2))
                    // = (pool-3)/pool  -- NO. Let me be precise.
                    // C(n,k) = n! / (k!(n-k)!)
                    // C(pool-1, 3) / C(pool, 3) = [(pool-1)! / (3!(pool-4)!)] / [pool! / (3!(pool-3)!)]
                    //                           = (pool-1)!(pool-3)! / (pool!(pool-4)!)
                    //                           = (pool-3) / pool
                    // So P(hit, 1 target, 3 draws) = 1 - (pool-3)/pool = 3/pool
                    let p_miss_single = (pool_size as f32 - 3.0) / pool_size as f32;
                    let p_miss = if stored_omen == 3 { // ABYSSAL_ECHOES
                        p_miss_single * p_miss_single // two independent draws
                    } else {
                        p_miss_single
                    };
                    1.0 - p_miss
                };

                if rng.gen::<f32>() < p_hit {
                    // Hit: place the desecrated target directly
                    if is_prefix {
                        let idx = item.prefix_count as usize;
                        item.prefix_families[idx] = fam;
                        item.prefix_tiers[idx] = 1;
                        item.prefix_count += 1;
                    } else {
                        let idx = item.suffix_count as usize;
                        item.suffix_families[idx] = fam;
                        item.suffix_tiers[idx] = 1;
                        item.suffix_count += 1;
                    }
                } else {
                    // Miss: place a random mod from the normal pool (same affix type)
                    if is_prefix {
                        let blocked: Vec<u16> = (0..item.prefix_count as usize)
                            .map(|i| item.prefix_families[i])
                            .filter(|&f| f != 0)
                            .collect();
                        let rng_val = rng.gen::<u64>();
                        if let Some((f, t)) = pool.sample_prefix(&blocked, 0, rng_val) {
                            let idx = item.prefix_count as usize;
                            item.prefix_families[idx] = f;
                            item.prefix_tiers[idx] = t;
                            item.prefix_count += 1;
                        }
                    } else {
                        let blocked: Vec<u16> = (0..item.suffix_count as usize)
                            .map(|i| item.suffix_families[i])
                            .filter(|&f| f != 0)
                            .collect();
                        let rng_val = rng.gen::<u64>();
                        if let Some((f, t)) = pool.sample_suffix(&blocked, 0, rng_val) {
                            let idx = item.suffix_count as usize;
                            item.suffix_families[idx] = f;
                            item.suffix_tiers[idx] = t;
                            item.suffix_count += 1;
                        }
                    }
                }
            } else {
                // No desecrated target missing — place any random mod (same affix type)
                if is_prefix {
                    let blocked: Vec<u16> = (0..item.prefix_count as usize)
                        .map(|i| item.prefix_families[i])
                        .filter(|&f| f != 0)
                        .collect();
                    let rng_val = rng.gen::<u64>();
                    if let Some((f, t)) = pool.sample_prefix(&blocked, 0, rng_val) {
                        let idx = item.prefix_count as usize;
                        item.prefix_families[idx] = f;
                        item.prefix_tiers[idx] = t;
                        item.prefix_count += 1;
                    }
                } else {
                    let blocked: Vec<u16> = (0..item.suffix_count as usize)
                        .map(|i| item.suffix_families[i])
                        .filter(|&f| f != 0)
                        .collect();
                    let rng_val = rng.gen::<u64>();
                    if let Some((f, t)) = pool.sample_suffix(&blocked, 0, rng_val) {
                        let idx = item.suffix_count as usize;
                        item.suffix_families[idx] = f;
                        item.suffix_tiers[idx] = t;
                        item.suffix_count += 1;
                    }
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
#[derive(Clone, Copy)]
enum TierRank {
    Best,   // Greater Essence: lowest tier number = highest power
    Mid,    // Normal Essence: median tier
    Worst,  // Lesser Essence: highest tier number = lowest power
}

/// Place a mod from the specified family using the ESSENCE pool's tier data.
/// Only places the mod if the family exists in the essence pool.
/// Returns true if the mod was placed, false if the family isn't in the essence pool.
fn add_essence_mod(item: &mut ItemState, family: u16, pool: &ModPool, rank: TierRank) -> bool {
    // Family MUST exist in the essence pool — no fallback to normal pool
    let in_ess_prefix = pool.essence_prefix_families.contains(&family);
    let in_ess_suffix = pool.essence_suffix_families.contains(&family);

    if !in_ess_prefix && !in_ess_suffix {
        return false; // Family not in essence pool
    }

    // Determine prefix vs suffix
    let place_as_prefix = if in_ess_prefix {
        pool.target_prefix_families.contains(&family) || !in_ess_suffix
    } else {
        false // only in suffix essence pool
    };

    let tier = if place_as_prefix {
        tier_by_rank(family, &pool.essence_prefix_families, &pool.essence_prefix_tiers, &rank)
    } else {
        tier_by_rank(family, &pool.essence_suffix_families, &pool.essence_suffix_tiers, &rank)
    };

    if place_as_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = family;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
        true
    } else if !place_as_prefix && item.suffix_count < pool.max_suffixes {
        let idx = item.suffix_count as usize;
        item.suffix_families[idx] = family;
        item.suffix_tiers[idx] = tier;
        item.suffix_count += 1;
        true
    } else {
        false
    }
}

/// Place a random mod from the essence pool (when target isn't in essence pool).
/// Used as the guaranteed essence mod — picks a random essence family.
fn add_random_essence_mod(item: &mut ItemState, pool: &ModPool, rank: &TierRank, rng: &mut impl Rng) {
    // Collect unique essence families
    let mut ess_fams: Vec<(u16, bool)> = Vec::new(); // (family, is_prefix)
    for &f in &pool.essence_prefix_families {
        if f != 0 && !item.has_family(f) && !ess_fams.iter().any(|(ef, _)| *ef == f) {
            ess_fams.push((f, true));
        }
    }
    for &f in &pool.essence_suffix_families {
        if f != 0 && !item.has_family(f) && !ess_fams.iter().any(|(ef, _)| *ef == f) {
            ess_fams.push((f, false));
        }
    }
    if ess_fams.is_empty() {
        return;
    }
    let (fam, is_prefix) = ess_fams[rng.gen_range(0..ess_fams.len())];
    let tier = if is_prefix {
        tier_by_rank(fam, &pool.essence_prefix_families, &pool.essence_prefix_tiers, rank)
    } else {
        tier_by_rank(fam, &pool.essence_suffix_families, &pool.essence_suffix_tiers, rank)
    };
    if is_prefix && item.prefix_count < pool.max_prefixes {
        let idx = item.prefix_count as usize;
        item.prefix_families[idx] = fam;
        item.prefix_tiers[idx] = tier;
        item.prefix_count += 1;
    } else if !is_prefix && item.suffix_count < pool.max_suffixes {
        let idx = item.suffix_count as usize;
        item.suffix_families[idx] = fam;
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
