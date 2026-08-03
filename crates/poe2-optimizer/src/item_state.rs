/// Compact item state for simulation (32 bytes, L1 cache-friendly).
///
/// Only tracks mod families and tiers — sufficient for all condition predicates
/// and strategy decisions. Full stat values are resolved after the optimizer
/// picks the winning strategy.
#[derive(Clone, Debug)]
#[repr(C)]
pub struct ItemState {
    pub rarity: u8,               // 0=Normal, 1=Magic, 2=Rare
    pub prefix_count: u8,         // 0-3
    pub suffix_count: u8,         // 0-3
    pub fractured_mask: u8,       // bit per mod slot (6 bits used)
    pub prefix_families: [u16; 3], // family IDs (0 = empty slot)
    pub suffix_families: [u16; 3], // family IDs (0 = empty slot)
    pub prefix_tiers: [u8; 3],    // tier of each prefix (0 = empty)
    pub suffix_tiers: [u8; 3],    // tier of each suffix (0 = empty)
    pub cost_spent: f32,          // cumulative chaos cost
    pub step_count: u16,          // steps taken so far
    pub _padding: [u8; 2],        // align to 32 bytes
}

impl ItemState {
    pub fn blank(ilvl: u8) -> Self {
        Self {
            rarity: 0,
            prefix_count: 0,
            suffix_count: 0,
            fractured_mask: 0,
            prefix_families: [0; 3],
            suffix_families: [0; 3],
            prefix_tiers: [0; 3],
            suffix_tiers: [0; 3],
            cost_spent: 0.0,
            step_count: 0,
            _padding: [0; 2],
        }
    }

    /// Total non-empty mod count.
    pub fn mod_count(&self) -> u8 {
        self.prefix_count + self.suffix_count
    }

    /// Check if a family is already on the item (blocked for new rolls).
    pub fn has_family(&self, family: u16) -> bool {
        self.prefix_families[..self.prefix_count as usize].contains(&family)
            || self.suffix_families[..self.suffix_count as usize].contains(&family)
    }

    /// Check if all target families are present (any tier).
    pub fn all_targets_hit(&self, target_families: &[u16]) -> bool {
        target_families.iter().all(|f| self.has_family(*f))
    }

    /// Check if all target families are present at required tier or better.
    pub fn all_targets_at_tier(&self, target_families: &[u16], max_tiers: &[u8]) -> bool {
        for (family, max_tier) in target_families.iter().zip(max_tiers.iter()) {
            let found = self.prefix_families[..self.prefix_count as usize]
                .iter()
                .zip(self.prefix_tiers.iter())
                .any(|(f, t)| *f == *family && *t <= *max_tier && *t > 0)
                || self.suffix_families[..self.suffix_count as usize]
                    .iter()
                    .zip(self.suffix_tiers.iter())
                    .any(|(f, t)| *f == *family && *t <= *max_tier && *t > 0);
            if !found {
                return false;
            }
        }
        true
    }

    /// Count how many target families are present on the item.
    pub fn targets_on_item(&self, target_families: &[u16]) -> u8 {
        target_families.iter().filter(|f| self.has_family(**f)).count() as u8
    }

    /// Check if item has a non-fractured, non-target mod that could be annulled.
    pub fn has_non_target_removable(&self, target_families: &[u16]) -> bool {
        for i in 0..self.prefix_count as usize {
            if (self.fractured_mask >> i) & 1 == 0
                && !target_families.contains(&self.prefix_families[i])
            {
                return true;
            }
        }
        for i in 0..self.suffix_count as usize {
            if (self.fractured_mask >> (i + 3)) & 1 == 0
                && !target_families.contains(&self.suffix_families[i])
            {
                return true;
            }
        }
        false
    }

    /// Count removable non-target mods.
    pub fn removable_non_targets(&self, target_families: &[u16]) -> u8 {
        let mut count = 0u8;
        for i in 0..self.prefix_count as usize {
            if (self.fractured_mask >> i) & 1 == 0
                && !target_families.contains(&self.prefix_families[i])
            {
                count += 1;
            }
        }
        for i in 0..self.suffix_count as usize {
            if (self.fractured_mask >> (i + 3)) & 1 == 0
                && !target_families.contains(&self.suffix_families[i])
            {
                count += 1;
            }
        }
        count
    }
}
