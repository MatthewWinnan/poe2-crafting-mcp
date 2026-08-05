/// Compact item state for simulation (fits in cache line).
///
/// Only tracks mod families and tiers — sufficient for all condition predicates
/// and strategy decisions. Full stat values are resolved after the optimizer
/// picks the winning strategy.

#[derive(Clone, Debug)]
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
    pub flags: u8,                // bit 0: desecrated, bit 1: divined, bit 2: has_essence_mod
                                   // bits 4-5: desecrate_omen (0=none, 1=sinistral_necro, 2=dextral_necro, 3=echoes)
}

impl ItemState {
    pub fn blank() -> Self {
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
            flags: 0,
        }
    }

    pub fn mod_count(&self) -> u8 {
        self.prefix_count + self.suffix_count
    }

    pub fn has_family(&self, family: u16) -> bool {
        self.prefix_families[..self.prefix_count as usize].contains(&family)
            || self.suffix_families[..self.suffix_count as usize].contains(&family)
    }

    pub fn all_targets_hit(&self, target_families: &[u16]) -> bool {
        target_families.iter().all(|f| self.has_family(*f))
    }

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

    pub fn targets_on_item(&self, target_families: &[u16]) -> u8 {
        target_families.iter().filter(|f| self.has_family(**f)).count() as u8
    }

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

    // Flag accessors
    pub fn is_desecrated(&self) -> bool {
        self.flags & 0x01 != 0
    }

    pub fn set_desecrated(&mut self, val: bool) {
        if val { self.flags |= 0x01; } else { self.flags &= !0x01; }
    }

    pub fn is_divined(&self) -> bool {
        self.flags & 0x02 != 0
    }

    pub fn set_divined(&mut self, val: bool) {
        if val { self.flags |= 0x02; } else { self.flags &= !0x02; }
    }

    pub fn has_essence_mod(&self) -> bool {
        self.flags & 0x04 != 0
    }

    pub fn set_essence_mod(&mut self, val: bool) {
        if val { self.flags |= 0x04; } else { self.flags &= !0x04; }
    }

    pub fn has_fractured_mod(&self) -> bool {
        self.fractured_mask != 0
    }

    /// Store omen used at desecrate step (consumed at bone, affects reveal).
    /// Encoded in bits 4-5: 0=none, 1=sinistral_necro, 2=dextral_necro, 3=echoes
    pub fn set_desecrate_omen(&mut self, val: u8) {
        self.flags = (self.flags & 0x0F) | (val << 4);
    }

    pub fn desecrate_omen(&self) -> u8 {
        (self.flags >> 4) & 0x03
    }
}
