-- PoE2 Crafting MCP — SQLite schema
-- Populated by etl.py from PoB vendor data + static sources.
-- Re-run etl.py whenever the PoB submodule is updated.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Item Bases ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS item_bases (
    name            TEXT PRIMARY KEY,
    slot            TEXT NOT NULL,      -- "Gloves", "Ring", "Weapon", etc.
    sub_type        TEXT,               -- "Armour", "Evasion", "ES", "Hybrid"
    req_level       INTEGER DEFAULT 0,
    req_str         INTEGER DEFAULT 0,
    req_dex         INTEGER DEFAULT 0,
    req_int         INTEGER DEFAULT 0,
    socket_limit    INTEGER DEFAULT 0,
    tags            TEXT,               -- JSON array: ["armour","gloves","str_armour"]
    implicit_mod_types TEXT,            -- JSON array of implicit mod type keys
    armour          INTEGER DEFAULT 0,
    evasion         INTEGER DEFAULT 0,
    energy_shield   INTEGER DEFAULT 0,
    ward            INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bases_slot     ON item_bases(slot);
CREATE INDEX IF NOT EXISTS idx_bases_level    ON item_bases(req_level);
CREATE INDEX IF NOT EXISTS idx_bases_sub_type ON item_bases(sub_type);

-- ── Item Mods ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS item_mods (
    id          TEXT NOT NULL,          -- e.g. "Strength1", "CriticalDamage3"
    category    TEXT NOT NULL,          -- "Item", "Jewel", "Runes", "Corruption", etc.
    mod_type    TEXT,                   -- "Prefix" | "Suffix"
    affix       TEXT,                   -- display suffix/prefix name
    stat_text   TEXT,                   -- human-readable stat line
    stat_min    REAL,                   -- numeric lower bound (NULL if non-numeric)
    stat_max    REAL,                   -- numeric upper bound
    req_level   INTEGER DEFAULT 0,
    group_name  TEXT,                   -- PoB group key (deduplication)
    mod_tags    TEXT,                   -- JSON array: ["attack","damage"]
    weight_keys TEXT,                   -- JSON array of item tags
    weight_vals TEXT,                   -- JSON array of spawn weights
    PRIMARY KEY (id, category)
);

CREATE INDEX IF NOT EXISTS idx_mods_category  ON item_mods(category);
CREATE INDEX IF NOT EXISTS idx_mods_mod_type  ON item_mods(mod_type);
CREATE INDEX IF NOT EXISTS idx_mods_group     ON item_mods(group_name);
CREATE INDEX IF NOT EXISTS idx_mods_level     ON item_mods(req_level);

CREATE VIRTUAL TABLE IF NOT EXISTS item_mods_fts USING fts5(
    id, stat_text, affix, mod_tags,
    content='item_mods',
    tokenize='unicode61'
);

-- ── Gems ──────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gems (
    id                  TEXT PRIMARY KEY,  -- "Metadata/Items/Gems/SkillGemIceNova"
    name                TEXT NOT NULL,
    gem_type            TEXT,              -- "Attack", "Spell", "Support", ""
    is_support          INTEGER DEFAULT 0, -- 1 if support gem
    tier                INTEGER DEFAULT 0,
    req_str             INTEGER DEFAULT 0,
    req_dex             INTEGER DEFAULT 0,
    req_int             INTEGER DEFAULT 0,
    natural_max_level   INTEGER DEFAULT 20,
    tags                TEXT,              -- JSON array of tag names
    tag_string          TEXT,              -- comma-separated display string
    weapon_requirements TEXT               -- "One Hand Mace, Two Hand Mace" etc.
);

CREATE INDEX IF NOT EXISTS idx_gems_name       ON gems(name);
CREATE INDEX IF NOT EXISTS idx_gems_is_support ON gems(is_support);
CREATE INDEX IF NOT EXISTS idx_gems_gem_type   ON gems(gem_type);

CREATE VIRTUAL TABLE IF NOT EXISTS gems_fts USING fts5(
    name, tags, tag_string, weapon_requirements,
    content='gems',
    tokenize='unicode61'
);

-- ── Unique Items ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS uniques (
    name        TEXT NOT NULL,
    slot        TEXT NOT NULL,  -- "gloves", "ring", "weapon1", etc. (PoB slot key)
    base_type   TEXT,
    source      TEXT,           -- league/drop note (e.g. "Drops from Trialmaster")
    variants    TEXT,           -- JSON array of variant names if any
    raw_text    TEXT,           -- full PoB item text block
    PRIMARY KEY (name, slot)
);

CREATE INDEX IF NOT EXISTS idx_uniques_slot      ON uniques(slot);
CREATE INDEX IF NOT EXISTS idx_uniques_base_type ON uniques(base_type);

CREATE VIRTUAL TABLE IF NOT EXISTS uniques_fts USING fts5(
    name, base_type, raw_text,
    content='uniques',
    tokenize='unicode61'
);

-- ── Passive Nodes ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS passive_nodes (
    node_id             INTEGER PRIMARY KEY,
    name                TEXT,
    display_name        TEXT,
    node_type           TEXT,           -- "Notable","Keystone","Normal","Socket",
                                        -- "ClassStart","AscendStart","JewelSocket"
    ascendancy          TEXT,           -- NULL or ascendancy class name
    class_start_index   INTEGER,        -- NULL or 0–6 (class index)
    is_jewel_socket     INTEGER DEFAULT 0,
    stats               TEXT,           -- JSON array of stat description strings
    x                   REAL,
    y                   REAL,
    group_id            INTEGER
);

CREATE INDEX IF NOT EXISTS idx_nodes_type        ON passive_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_ascendancy  ON passive_nodes(ascendancy);
CREATE INDEX IF NOT EXISTS idx_nodes_class_start ON passive_nodes(class_start_index);

CREATE VIRTUAL TABLE IF NOT EXISTS passive_nodes_fts USING fts5(
    name, stats,
    content='passive_nodes',
    tokenize='unicode61'
);

-- ── Currencies ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS currencies (
    name        TEXT PRIMARY KEY,
    category    TEXT NOT NULL,  -- "Orb","Quality","Essence","Rune","SoulCore",
                                -- "Distilled","Fragment","Catalyst","Other"
    subcategory TEXT,           -- finer grouping within category
    effect      TEXT,           -- human-readable effect summary
    trade_id    TEXT            -- poe.trade/poe.ninja slug
);

CREATE INDEX IF NOT EXISTS idx_currencies_category ON currencies(category);

-- ── ETL Metadata ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS etl_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at      TEXT DEFAULT (datetime('now')),
    pob_version TEXT,
    row_counts  TEXT    -- JSON: {"item_bases": 1755, ...}
);
