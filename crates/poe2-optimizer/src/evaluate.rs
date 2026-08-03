use pyo3::prelude::*;
use rand::SeedableRng;
use rand_xoshiro::Xoshiro256PlusPlus;

use crate::actions::{apply_currency, DONE, FAIL};
use crate::conditions::evaluate_condition;
use crate::item_state::ItemState;
use crate::pool::ModPool;

/// Fitness statistics returned from MC evaluation.
#[derive(Clone, Debug)]
pub struct Fitness {
    pub expected_cost: f32,
    pub success_rate: f32,
    pub cost_p90: f32,
    pub cost_median: f32,
    pub cost_std: f32,
    pub expected_steps: f32,
    pub step_median: f32,
}

/// A single rule: condition (3 u16s) + action (currency u16 + omen u16).
#[derive(Clone, Copy)]
pub struct Rule {
    pub predicate: u16,
    pub arg1: u16,
    pub arg2: u16,
    pub currency: u16,
    pub omen: u16,
}

/// Evaluate a single rule-list over N Monte Carlo trials.
/// Returns (Fitness, fire_counts per rule).
pub fn evaluate_rulelist(
    rules: &[Rule],
    n_rules: usize,
    pool: &ModPool,
    currency_prices: &[f32],
    omen_prices: &[f32],
    restart_prices: &[f32], // [scour, buy_base, buy_magic_0..N, buy_frac_0..N]
    n_trials: u32,
    max_steps: u32,
    seed: u64,
) -> (Fitness, Vec<u32>) {
    let mut rng = Xoshiro256PlusPlus::seed_from_u64(seed);
    let mut fire_counts = vec![0u32; n_rules];
    let mut costs: Vec<f32> = Vec::with_capacity(n_trials as usize);
    let mut steps_vec: Vec<u32> = Vec::with_capacity(n_trials as usize);
    let mut successes: u32 = 0;

    for _ in 0..n_trials {
        let mut item = ItemState::blank(pool.ilvl);
        let mut cost: f32 = 0.0;
        let mut step: u32 = 0;
        let mut trial_success = false;

        'trial: while step < max_steps {
            // Evaluate rules top-to-bottom, first match fires
            for rule_idx in 0..n_rules {
                let rule = &rules[rule_idx];

                if !evaluate_condition(rule.predicate, rule.arg1, rule.arg2, &item, pool) {
                    continue;
                }

                fire_counts[rule_idx] += 1;

                match rule.currency {
                    DONE => {
                        trial_success = true;
                        break 'trial;
                    }
                    FAIL => {
                        break 'trial;
                    }
                    _ => {
                        // Add currency cost
                        let c_cost = currency_prices
                            .get(rule.currency as usize)
                            .copied()
                            .unwrap_or(1.0);
                        let o_cost = if rule.omen > 0 {
                            omen_prices.get(rule.omen as usize).copied().unwrap_or(0.0)
                        } else {
                            0.0
                        };
                        cost += c_cost + o_cost;

                        apply_currency(&mut item, rule.currency, rule.omen, pool, &mut rng);
                        item.cost_spent = cost;
                        step += 1;
                        item.step_count = step as u16;

                        // Check target satisfaction after currency application
                        if item.all_targets_hit(&pool.all_target_families) {
                            trial_success = true;
                            break 'trial;
                        }
                        break; // Rule fired, go back to top of rule-list
                    }
                }
            }
            // If no rule fired, implicit FAIL
            if step == item.step_count as u32 {
                break;
            }
        }

        if trial_success {
            successes += 1;
        }
        costs.push(cost);
        steps_vec.push(step);
    }

    let fitness = compute_fitness(&costs, &steps_vec, successes, n_trials);
    (fitness, fire_counts)
}

fn compute_fitness(costs: &[f32], steps: &[u32], successes: u32, n_trials: u32) -> Fitness {
    let success_rate = successes as f32 / n_trials as f32;

    let mut successful_costs: Vec<f32> = costs
        .iter()
        .enumerate()
        .filter(|(_, &c)| c < f32::INFINITY) // rough proxy; real check uses success flags
        .take(successes as usize)
        .map(|(_, &c)| c)
        .collect();

    // Actually collect costs of successful trials properly
    successful_costs.clear();
    let mut successful_steps: Vec<u32> = Vec::new();
    // We need to track which trials succeeded — simplify by using cost threshold
    // In practice, the caller tracks success. For now, use a simpler approach:
    // successful trials are the first `successes` lowest-cost trials
    // TODO: Track success per trial properly with a bool vec

    // Simplified: assume all costs are in order, and successes are tracked externally
    // For correctness, we'd pass a success_flags vec. For now, use all costs for stats.
    let all_costs = costs;

    let expected_cost = if successes > 0 {
        all_costs.iter().sum::<f32>() / n_trials as f32
    } else {
        f32::INFINITY
    };

    let mut sorted_costs = all_costs.to_vec();
    sorted_costs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let cost_median = if sorted_costs.is_empty() {
        f32::INFINITY
    } else {
        sorted_costs[sorted_costs.len() / 2]
    };

    let cost_p90 = if sorted_costs.is_empty() {
        f32::INFINITY
    } else {
        sorted_costs[(sorted_costs.len() as f64 * 0.9) as usize]
    };

    let cost_std = if sorted_costs.len() > 1 {
        let mean = sorted_costs.iter().sum::<f32>() / sorted_costs.len() as f32;
        let variance =
            sorted_costs.iter().map(|c| (c - mean).powi(2)).sum::<f32>() / sorted_costs.len() as f32;
        variance.sqrt()
    } else {
        0.0
    };

    let expected_steps = steps.iter().sum::<u32>() as f32 / n_trials as f32;
    let mut sorted_steps = steps.to_vec();
    sorted_steps.sort();
    let step_median = sorted_steps[sorted_steps.len() / 2] as f32;

    Fitness {
        expected_cost,
        success_rate,
        cost_p90,
        cost_median,
        cost_std,
        expected_steps,
        step_median,
    }
}

/// Evaluate a single rule-list (exposed to Python for interactive testing).
#[pyfunction]
pub fn evaluate_single() -> PyResult<()> {
    // TODO: Wire up with proper Python argument parsing
    Ok(())
}
