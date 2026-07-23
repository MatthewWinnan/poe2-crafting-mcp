# PoE2 Crafting MCP Server

An MCP (Model Context Protocol) server that acts as a crafting and gear advisor for Path of Exile 2. Given your current build, budget, and goal, it determines the optimal path forward — buy or craft — grounded in community meta data and live economy pricing.

## Features (MVP)

- **Build Import:** Paste a Path of Building PoE2 share code to load your character
- **DPS Simulation:** Compare items, see exact stat changes via PoB's calculation engine
- **Crafting Recipes:** Get step-by-step crafting instructions with probabilities and expected costs
- **Price Checking:** Live economy data from poe.show and poe.ninja
- **Buy vs Craft:** Automatic comparison of buying on trade vs crafting yourself

## Setup

```bash
# Enter dev shell (requires Nix with flakes)
nix develop
# or with direnv:
direnv allow

# Clone PoB-PoE2 (first time only)
git submodule update --init

# Run tests
pytest

# Start the MCP server
poe2-craft
```

## Architecture

See the [planning docs](docs/) or the full design in the obsidian vault.

## License

MIT
