use crate::item_state::ItemState;
use crate::pool::ModPool;

/// Predicate IDs matching the Python Condition.predicate field.
/// Serialized as u16 in the rules array passed from Python.
pub const RARITY_IS: u16 = 0;
pub const HAS_ANY_TARGET: u16 = 1;
pub const HAS_TARGET: u16 = 2;
pub const ALL_TARGETS_HIT: u16 = 3;
pub const ALL_TARGETS_AT_TIER: u16 = 4;
pub const MISSING_TARGET_PREFIX: u16 = 5;
pub const MISSING_TARGET_SUFFIX: u16 = 6;
pub const HAS_NON_TARGET_REMOVABLE: u16 = 7;
pub const TARGETS_ON_ITEM_GTE: u16 = 8;
pub const OPEN_PREFIX_GTE: u16 = 9;
pub const OPEN_SUFFIX_GTE: u16 = 10;
pub const MOD_COUNT_GTE: u16 = 11;
pub const MOD_COUNT_LTE: u16 = 12;
pub const COST_SPENT_GTE: u16 = 13;
pub const STEP_COUNT_GTE: u16 = 14;
pub const REMOVABLE_GT_TARGETS: u16 = 15;
pub const PREFIX_FULL_NO_TARGET_PREFIX: u16 = 16;
pub const SUFFIX_FULL_NO_TARGET_SUFFIX: u16 = 17;
pub const ALWAYS_TRUE: u16 = 255; // DEFAULT rule

/// Evaluate a condition predicate against the current item state.
///
/// Conditions are encoded as (predicate_id: u16, arg1: u16, arg2: u16).
/// All evaluation is integer/float comparison — no allocations, branch-predictor friendly.
pub fn evaluate_condition(
    predicate: u16,
    arg1: u16,
    arg2: u16,
    item: &ItemState,
    pool: &ModPool,
) -> bool {
    match predicate {
        RARITY_IS => item.rarity == arg1 as u8,

        HAS_ANY_TARGET => item.targets_on_item(&pool.all_target_families) > 0,

        HAS_TARGET => item.has_family(arg1),

        ALL_TARGETS_HIT => item.all_targets_hit(&pool.all_target_families),

        ALL_TARGETS_AT_TIER => {
            item.all_targets_at_tier(&pool.all_target_families, &pool.target_max_tiers)
        }

        MISSING_TARGET_PREFIX => {
            pool.target_prefix_families.iter().any(|f| !item.has_family(*f))
        }

        MISSING_TARGET_SUFFIX => {
            pool.target_suffix_families.iter().any(|f| !item.has_family(*f))
        }

        HAS_NON_TARGET_REMOVABLE => item.has_non_target_removable(&pool.all_target_families),

        TARGETS_ON_ITEM_GTE => item.targets_on_item(&pool.all_target_families) >= arg1 as u8,

        OPEN_PREFIX_GTE => {
            let max_p = if item.rarity == 1 { 1 } else { pool.max_prefixes };
            (max_p - item.prefix_count) >= arg1 as u8
        }

        OPEN_SUFFIX_GTE => {
            let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
            (max_s - item.suffix_count) >= arg1 as u8
        }

        MOD_COUNT_GTE => item.mod_count() >= arg1 as u8,

        MOD_COUNT_LTE => item.mod_count() <= arg1 as u8,

        COST_SPENT_GTE => {
            // Threshold encoded as f32 bits split across arg1 (high) and arg2 (low)
            let bits = (arg1 as u32) << 16 | arg2 as u32;
            item.cost_spent >= f32::from_bits(bits)
        }

        STEP_COUNT_GTE => item.step_count >= arg1,

        REMOVABLE_GT_TARGETS => {
            let removable = item.removable_non_targets(&pool.all_target_families);
            let targets = item.targets_on_item(&pool.all_target_families);
            removable > targets
        }

        PREFIX_FULL_NO_TARGET_PREFIX => {
            let max_p = if item.rarity == 1 { 1 } else { pool.max_prefixes };
            item.prefix_count >= max_p
                && !pool.target_prefix_families.iter().any(|f| {
                    item.prefix_families[..item.prefix_count as usize].contains(f)
                })
        }

        SUFFIX_FULL_NO_TARGET_SUFFIX => {
            let max_s = if item.rarity == 1 { 1 } else { pool.max_suffixes };
            item.suffix_count >= max_s
                && !pool.target_suffix_families.iter().any(|f| {
                    item.suffix_families[..item.suffix_count as usize].contains(f)
                })
        }

        ALWAYS_TRUE => true,

        _ => false,
    }
}
