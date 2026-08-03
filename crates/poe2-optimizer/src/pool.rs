/// Pre-computed mod pool data, passed once from Python at optimization start.
///
/// Pools are encoded as flat arrays for cache-friendly weighted sampling.
/// Binary search on cumulative sums gives O(log n) random mod selection.

pub struct ModPool {
    // Prefix pool
    pub prefix_weights: Vec<u32>,
    pub prefix_cumsum: Vec<u64>,
    pub prefix_families: Vec<u16>,
    pub prefix_tiers: Vec<u8>,
    pub prefix_req_levels: Vec<u8>,
    pub prefix_total_weight: u64,

    // Suffix pool
    pub suffix_weights: Vec<u32>,
    pub suffix_cumsum: Vec<u64>,
    pub suffix_families: Vec<u16>,
    pub suffix_tiers: Vec<u8>,
    pub suffix_req_levels: Vec<u8>,
    pub suffix_total_weight: u64,

    // Target specification
    pub target_prefix_families: Vec<u16>,
    pub target_suffix_families: Vec<u16>,
    pub target_max_tiers: Vec<u8>,
    /// All target families (prefix + suffix) for fast lookup
    pub all_target_families: Vec<u16>,

    // Item metadata
    pub ilvl: u8,
    pub max_prefixes: u8, // 1 for Magic, 3 for Rare
    pub max_suffixes: u8,
}

impl ModPool {
    /// Sample a random prefix from the pool, respecting family blocking.
    /// Uses rejection sampling — given typical blocking removes <15% of pool,
    /// expected attempts before acceptance is ~1.18.
    pub fn sample_prefix(
        &self,
        blocked_families: &[u16],
        min_req_level: u8,
        rng_val: u64,
    ) -> Option<(u16, u8)> {
        // Fast path: no blocking, no level filter
        if blocked_families.is_empty() && min_req_level == 0 {
            let idx = self.weighted_sample_prefix(rng_val);
            return Some((self.prefix_families[idx], self.prefix_tiers[idx]));
        }

        // Rejection sampling (bounded retries)
        let mut val = rng_val;
        for _ in 0..50 {
            let idx = self.weighted_sample_prefix(val);
            let family = self.prefix_families[idx];
            let req_lv = self.prefix_req_levels[idx];

            if !blocked_families.contains(&family) && req_lv >= min_req_level {
                return Some((family, self.prefix_tiers[idx]));
            }
            // Remix the rng value for next attempt
            val = val.wrapping_mul(6364136223846793005).wrapping_add(1);
        }
        None // Pool exhausted (shouldn't happen in practice)
    }

    /// Sample a random suffix from the pool, respecting family blocking.
    pub fn sample_suffix(
        &self,
        blocked_families: &[u16],
        min_req_level: u8,
        rng_val: u64,
    ) -> Option<(u16, u8)> {
        if blocked_families.is_empty() && min_req_level == 0 {
            let idx = self.weighted_sample_suffix(rng_val);
            return Some((self.suffix_families[idx], self.suffix_tiers[idx]));
        }

        let mut val = rng_val;
        for _ in 0..50 {
            let idx = self.weighted_sample_suffix(val);
            let family = self.suffix_families[idx];
            let req_lv = self.suffix_req_levels[idx];

            if !blocked_families.contains(&family) && req_lv >= min_req_level {
                return Some((family, self.suffix_tiers[idx]));
            }
            val = val.wrapping_mul(6364136223846793005).wrapping_add(1);
        }
        None
    }

    /// Binary search on cumulative sum for weighted random selection.
    fn weighted_sample_prefix(&self, rng_val: u64) -> usize {
        let target = rng_val % self.prefix_total_weight;
        self.prefix_cumsum.partition_point(|&w| w <= target)
    }

    fn weighted_sample_suffix(&self, rng_val: u64) -> usize {
        let target = rng_val % self.suffix_total_weight;
        self.suffix_cumsum.partition_point(|&w| w <= target)
    }
}
