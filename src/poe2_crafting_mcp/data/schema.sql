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

-- ── Essences ────────────────────────────────────────────────────────────────
-- Scraped from poe2db.tw/us/Essence. Each row = one essence + one item slot effect.
-- An essence may have multiple rows (one per applicable item slot).

CREATE TABLE IF NOT EXISTS essences (
    name        TEXT NOT NULL,       -- "Lesser Essence of the Body"
    tier        TEXT NOT NULL,       -- "Lesser", "Normal", "Greater", "Perfect", "Corrupted", "Alloy"
    base_name   TEXT NOT NULL,       -- "Body", "Mind", "Flames", etc.
    effect_type TEXT NOT NULL,       -- "upgrade" (Magic→Rare) or "swap" (remove+add on Rare)
    item_slots  TEXT NOT NULL,       -- applicable slots, e.g. "Armour or Belt"
    stat_text   TEXT NOT NULL,       -- mod text, e.g. "+(30-39) to maximum Life"
    stat_min    REAL,
    stat_max    REAL,
    PRIMARY KEY (name, item_slots)
);

CREATE INDEX IF NOT EXISTS idx_essences_tier      ON essences(tier);
CREATE INDEX IF NOT EXISTS idx_essences_base_name ON essences(base_name);

CREATE VIRTUAL TABLE IF NOT EXISTS essences_fts USING fts5(
    name, base_name, stat_text, item_slots,
    content='essences',
    tokenize='unicode61'
);

-- ── Prices (poe.ninja cache) ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prices (
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,   -- "currency","fragment","unique","base","gem"
    league        TEXT NOT NULL,
    chaos_value   REAL,
    divine_value  REAL,
    listing_count INTEGER,
    fetched_at    TEXT NOT NULL,   -- ISO datetime (UTC)
    PRIMARY KEY (name, category, league)
);

CREATE INDEX IF NOT EXISTS idx_prices_league   ON prices(league);
CREATE INDEX IF NOT EXISTS idx_prices_category ON prices(category);

-- ── Economy Meta (key/value store) ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS economy_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Keys used:
--   active_league     — league we're targeting (user-set or auto-detected)
--   prices_fetched_at — ISO datetime of last price refresh
--   etl_league        — league active when ETL last ran
--   etl_ran_at        — ISO datetime of last ETL run

-- ── Trade API Stat Index ──────────────────────────────────────────────────────
-- Populated by fetching GET /api/trade2/data/stats from the GGG trade site.
-- Enables stat-ID lookup for stat-filtered trade searches (e.g. T1 energy shield).

CREATE TABLE IF NOT EXISTS trade_stats (
    stat_id    TEXT PRIMARY KEY,
    stat_text  TEXT NOT NULL,
    stat_type  TEXT NOT NULL,   -- "explicit", "implicit", "pseudo", "enchant", etc.
    fetched_at TEXT NOT NULL    -- ISO datetime (UTC)
);

CREATE INDEX IF NOT EXISTS idx_trade_stats_type ON trade_stats(stat_type);

CREATE VIRTUAL TABLE IF NOT EXISTS trade_stats_fts USING fts5(
    stat_id, stat_text,
    content='trade_stats',
    tokenize='unicode61'
);

-- ── Concepts / Keyword Definitions ───────────────────────────────────────────
-- Seeded from concepts.py during ETL; patchable at runtime via update_concept().
-- source values: "manual", "PoB:ConfigOptions", "PoB:SkillTypes", "PoB:Gems", "poe2wiki"
-- league_version: NULL = applies to all leagues; set to league name for league-specific entries.

CREATE TABLE IF NOT EXISTS concepts (
    name            TEXT PRIMARY KEY,
    category        TEXT NOT NULL,      -- damage_type, ailment, keyword, mechanic, etc.
    summary         TEXT NOT NULL DEFAULT '',
    mechanics       TEXT NOT NULL DEFAULT '',
    formula         TEXT NOT NULL DEFAULT '',
    see_also        TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    source          TEXT NOT NULL DEFAULT 'manual',
    league_version  TEXT,               -- NULL = all leagues
    updated_at      TEXT NOT NULL       -- ISO datetime (UTC)
);

CREATE INDEX IF NOT EXISTS idx_concepts_category ON concepts(category);
CREATE INDEX IF NOT EXISTS idx_concepts_source   ON concepts(source);

CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
    name, category, summary, mechanics,
    content='concepts',
    tokenize='unicode61'
);

-- ── Item Descriptions ────────────────────────────────────────────────────────
-- Seeded from item_descriptions.py during ETL; patchable at runtime.
-- category values: "base", "currency", "gem", "unique", "mechanic_item"
-- source values: "manual", "poe2wiki", "poe2db"
-- league_version: NULL = applies to all leagues; set to league name for league-specific entries.

CREATE TABLE IF NOT EXISTS item_descriptions (
    name            TEXT PRIMARY KEY,
    category        TEXT NOT NULL,      -- "base", "currency", "gem", "unique", "mechanic_item"
    description     TEXT NOT NULL DEFAULT '',   -- what it is / what it's used for
    crafting_notes  TEXT NOT NULL DEFAULT '',   -- notable mods, best ilvl, typical uses
    drop_notes      TEXT NOT NULL DEFAULT '',   -- where it drops / league source
    see_also        TEXT NOT NULL DEFAULT '[]', -- JSON array of related names
    source          TEXT NOT NULL DEFAULT 'manual',
    league_version  TEXT,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_item_desc_category ON item_descriptions(category);
CREATE INDEX IF NOT EXISTS idx_item_desc_source   ON item_descriptions(source);

CREATE VIRTUAL TABLE IF NOT EXISTS item_descriptions_fts USING fts5(
    name, category, description, crafting_notes,
    content='item_descriptions',
    tokenize='unicode61'
);

-- ── ETL Metadata ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS etl_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at      TEXT DEFAULT (datetime('now')),
    pob_version TEXT,
    row_counts  TEXT    -- JSON: {"item_bases": 1755, ...}
);
