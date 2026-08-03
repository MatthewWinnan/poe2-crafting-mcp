use rand::Rng;

use crate::item_state::ItemState;
use crate::pool::ModPool;

/// Currency action IDs — matched from Python serialization.
pub const DONE: u16 = 0;
pub const FAIL: u16 = 1;
pub const SCOUR: u16 = 2;
pub const BUY_BASE: u16 = 3;
pub const BUY_MAGIC: u16 = 4;   // arg1 = family index into targets
pub const BUY_FRACTURED: u16 = 5; // arg1 = family index into targets
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

/// Omen IDs
pub const NO_OMEN: u16 = 0;
pub const SINISTRAL_EXALTATION: u16 = 1;  // force prefix
pub const DEXTRAL_EXALTATION: u16 = 2;    // force suffix
pub const GREATER_EXALTATION: u16 = 3;    // add 2 mods
pub const SINISTRAL_ANNULMENT: u16 = 4;   // remove prefix only
pub const DEXTRAL_ANNULMENT: u16 = 5;     // remove suffix only
pub const SINISTRAL_CORONATION: u16 = 6;  // regal adds prefix
pub const DEXTRAL_CORONATION: u16 = 7;    // regal adds suffix

/// Apply a crafting currency to the item state.
/// Returns true if the action was successfully applied.
pub fn apply_currency(
    item: &mut ItemState,
    currency: u16,
    omen: u16,
    pool: &ModPool,
    rng: &mut impl Rng,
) -> bool {
    match currency {
        SCOUR | BUY_BASE => {
            *item = ItemState::blank(pool.ilvl);
            true
        }

        TRANSMUTE | GREATER_TRANSMUTE | PERFECT_TRANSMUTE => {
            if item.rarity != 0 {
                return false;
            }
            item.rarity = 1; // Normal → Magic
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, NO_OMEN, rng);
            true
        }

        ALTERATION => {
            if item.rarity != 1 {
                return false;
            }
            // Reroll magic: clear + add 1 mod
            clear_mods(item);
            add_random_mod(item, pool, 0, NO_OMEN, rng);
            true
        }

        AUGMENT | GREATER_AUGMENT | PERFECT_AUGMENT => {
            if item.rarity != 1 {
                return false;
            }
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, NO_OMEN, rng);
            true
        }

        REGAL | GREATER_REGAL | PERFECT_REGAL => {
            if item.rarity != 1 {
                return false;
            }
            item.rarity = 2; // Magic → Rare
            let min_lv = min_level_for_currency(currency);
            let effective_omen = match omen {
                SINISTRAL_CORONATION => SINISTRAL_EXALTATION,
                DEXTRAL_CORONATION => DEXTRAL_EXALTATION,
                _ => NO_OMEN,
            };
            add_random_mod(item, pool, min_lv, effective_omen, rng);
            true
        }

        EXALTED | GREATER_EXALTED | PERFECT_EXALTED => {
            if item.rarity != 2 {
                return false;
            }
            let min_lv = min_level_for_currency(currency);
            add_random_mod(item, pool, min_lv, omen, rng);
            true
        }

        ANNULMENT => {
            if item.mod_count() == 0 {
                return false;
            }
            remove_random_mod(item, omen, rng);
            true
        }

        CHAOS | GREATER_CHAOS | PERFECT_CHAOS => {
            if item.rarity != 2 {
                return false;
            }
            let min_lv = min_level_for_currency(currency);
            // Remove 1 random non-fractured mod
            remove_random_mod(item, NO_OMEN, rng);
            // Add 1 random mod
            add_random_mod(item, pool, min_lv, NO_OMEN, rng);
            true
        }

        ALCHEMY => {
            if item.rarity == 2 {
                return false;
            }
            item.rarity = 2; // → Rare
            clear_mods(item);
            // Fill with 4-6 random mods
            let n_mods = rng.gen_range(4u8..=6u8);
            for _ in 0..n_mods {
                if item.mod_count() >= 6 {
                    break;
                }
                add_random_mod(item, pool, 0, NO_OMEN, rng);
            }
            true
        }

        _ => false,
    }
}

/// Get minimum required mod level for Greater/Perfect currency variants.
fn min_level_for_currency(currency: u16) -> u8 {
    match currency {
        GREATER_TRANSMUTE | GREATER_AUGMENT | GREATER_REGAL | GREATER_EXALTED | GREATER_CHAOS => 35,
        PERFECT_TRANSMUTE | PERFECT_AUGMENT | PERFECT_REGAL | PERFECT_EXALTED | PERFECT_CHAOS => 50,
        _ => 0,
    }
}

/// Add a random mod to the item, respecting family blocking and omen targeting.
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

    // Omen targeting
    let force_prefix = omen == SINISTRAL_EXALTATION;
    let force_suffix = omen == DEXTRAL_EXALTATION;

    // Collect blocked families
    let blocked: Vec<u16> = item.prefix_families[..item.prefix_count as usize]
        .iter()
        .chain(item.suffix_families[..item.suffix_count as usize].iter())
        .copied()
        .filter(|&f| f != 0)
        .collect();

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
        // Natural selection: pick prefix or suffix weighted by available pool weight
        let do_prefix = if !prefix_open {
            false
        } else if !suffix_open {
            true
        } else {
            // Weight by total pool weight (approximation — doesn't account for blocking)
            let total = pool.prefix_total_weight + pool.suffix_total_weight;
            (rng_val % total) < pool.prefix_total_weight
        };

        if do_prefix {
            if let Some((family, tier)) = pool.sample_prefix(&blocked, min_req_level, rng_val) {
                let idx = item.prefix_count as usize;
                item.prefix_families[idx] = family;
                item.prefix_tiers[idx] = tier;
                item.prefix_count += 1;
            }
        } else {
            if let Some((family, tier)) = pool.sample_suffix(&blocked, min_req_level, rng_val) {
                let idx = item.suffix_count as usize;
                item.suffix_families[idx] = family;
                item.suffix_tiers[idx] = tier;
                item.suffix_count += 1;
            }
        }
    }
}

/// Remove a random non-fractured mod from the item.
fn remove_random_mod(item: &mut ItemState, omen: u16, rng: &mut impl Rng) {
    let force_prefix = omen == SINISTRAL_ANNULMENT;
    let force_suffix = omen == DEXTRAL_ANNULMENT;

    // Collect removable indices
    let mut removable: Vec<(bool, usize)> = Vec::new(); // (is_prefix, slot_index)

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

    if is_prefix {
        // Shift remaining prefixes down
        for i in idx..2 {
            item.prefix_families[i] = item.prefix_families[i + 1];
            item.prefix_tiers[i] = item.prefix_tiers[i + 1];
        }
        item.prefix_families[2] = 0;
        item.prefix_tiers[2] = 0;
        item.prefix_count -= 1;
    } else {
        for i in idx..2 {
            item.suffix_families[i] = item.suffix_families[i + 1];
            item.suffix_tiers[i] = item.suffix_tiers[i + 1];
        }
        item.suffix_families[2] = 0;
        item.suffix_tiers[2] = 0;
        item.suffix_count -= 1;
    }
}

/// Clear all non-fractured mods (for alteration, alchemy reroll).
fn clear_mods(item: &mut ItemState) {
    // Keep fractured mods, clear the rest
    if item.fractured_mask == 0 {
        item.prefix_count = 0;
        item.suffix_count = 0;
        item.prefix_families = [0; 3];
        item.suffix_families = [0; 3];
        item.prefix_tiers = [0; 3];
        item.suffix_tiers = [0; 3];
    } else {
        // Compact fractured mods to front
        let mut new_pc = 0u8;
        let mut new_sc = 0u8;
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
}
