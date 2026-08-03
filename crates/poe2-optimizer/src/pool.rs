/// Pre-computed mod pool data, passed once from Python at optimization start.

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
    pub all_target_families: Vec<u16>,

    // Item metadata
    pub ilvl: u8,
    pub max_prefixes: u8,
    pub max_suffixes: u8,
}

impl ModPool {
    /// Sample a random prefix, respecting family blocking.
    pub fn sample_prefix(
        &self,
        blocked_families: &[u16],
        min_req_level: u8,
        rng_val: u64,
    ) -> Option<(u16, u8)> {
        if self.prefix_families.is_empty() || self.prefix_total_weight == 0 {
            return None;
        }

        let mut val = rng_val;
        for _ in 0..50 {
            let idx = self.weighted_sample_prefix(val);
            if idx >= self.prefix_families.len() {
                return None;
            }
            let family = self.prefix_families[idx];
            let req_lv = self.prefix_req_levels[idx];

            if !blocked_families.contains(&family) && req_lv >= min_req_level {
                return Some((family, self.prefix_tiers[idx]));
            }
            val = val.wrapping_mul(6364136223846793005).wrapping_add(1);
        }
        None
    }

    /// Sample a random suffix, respecting family blocking.
    pub fn sample_suffix(
        &self,
        blocked_families: &[u16],
        min_req_level: u8,
        rng_val: u64,
    ) -> Option<(u16, u8)> {
        if self.suffix_families.is_empty() || self.suffix_total_weight == 0 {
            return None;
        }

        let mut val = rng_val;
        for _ in 0..50 {
            let idx = self.weighted_sample_suffix(val);
            if idx >= self.suffix_families.len() {
                return None;
            }
            let family = self.suffix_families[idx];
            let req_lv = self.suffix_req_levels[idx];

            if !blocked_families.contains(&family) && req_lv >= min_req_level {
                return Some((family, self.suffix_tiers[idx]));
            }
            val = val.wrapping_mul(6364136223846793005).wrapping_add(1);
        }
        None
    }

    fn weighted_sample_prefix(&self, rng_val: u64) -> usize {
        let target = rng_val % self.prefix_total_weight;
        self.prefix_cumsum.partition_point(|&w| w <= target)
    }

    fn weighted_sample_suffix(&self, rng_val: u64) -> usize {
        let target = rng_val % self.suffix_total_weight;
        self.suffix_cumsum.partition_point(|&w| w <= target)
    }
}
