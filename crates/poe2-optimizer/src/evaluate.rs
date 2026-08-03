/// Monte Carlo evaluation of a single rule-list.

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

/// Result of evaluating one rule-list.
pub struct EvalResult {
    pub fitness: Fitness,
    pub fire_on_success: Vec<u32>,
    pub fire_on_failure: Vec<u32>,
}

/// Evaluate a single rule-list over N Monte Carlo trials.
pub fn evaluate_rulelist(
    rules: &[Rule],
    n_rules: usize,
    pool: &ModPool,
    prices: &[f32],   // flat array: [currencies..., omens...]
    max_currency_id: usize,
    n_trials: u32,
    max_steps: u32,
    seed: u64,
) -> EvalResult {
    let mut rng = Xoshiro256PlusPlus::seed_from_u64(seed);
    let mut fire_on_success = vec![0u32; n_rules];
    let mut fire_on_failure = vec![0u32; n_rules];
    let mut trial_fires = vec![0u32; n_rules];

    let mut costs: Vec<f32> = Vec::with_capacity(n_trials as usize);
    let mut successful_costs: Vec<f32> = Vec::new();
    let mut total_steps: u64 = 0;
    let mut successes: u32 = 0;

    for _ in 0..n_trials {
        let mut item = ItemState::blank();
        let mut step: u32 = 0;
        let mut trial_success = false;

        // Reset per-trial fire counts
        for f in trial_fires.iter_mut() {
            *f = 0;
        }

        'trial: while step < max_steps {
            // Evaluate rules top-to-bottom, first match fires
            let mut any_fired = false;
            for rule_idx in 0..n_rules {
                let rule = &rules[rule_idx];

                if !evaluate_condition(rule.predicate, rule.arg1, rule.arg2, &item, pool) {
                    continue;
                }

                trial_fires[rule_idx] += 1;
                any_fired = true;

                match rule.currency {
                    DONE => {
                        trial_success = true;
                        break 'trial;
                    }
                    FAIL => {
                        break 'trial;
                    }
                    _ => {
                        // Get currency cost
                        let c_cost = if (rule.currency as usize) < prices.len() {
                            prices[rule.currency as usize]
                        } else {
                            1.0
                        };
                        // Get omen cost (offset by max_currency_id)
                        let o_cost = if rule.omen > 0 {
                            let omen_idx = max_currency_id + rule.omen as usize;
                            if omen_idx < prices.len() { prices[omen_idx] } else { 0.0 }
                        } else {
                            0.0
                        };

                        item.cost_spent += c_cost + o_cost;
                        apply_currency(&mut item, rule.currency, rule.omen, pool, &mut rng);
                        step += 1;
                        item.step_count = step as u16;

                        // Check target satisfaction
                        if item.all_targets_hit(&pool.all_target_families) {
                            trial_success = true;
                            break 'trial;
                        }
                        break; // Rule fired, restart from top of rule-list
                    }
                }
            }

            if !any_fired {
                break; // No rule matched — implicit FAIL
            }
        }

        // Accumulate per-rule credits
        if trial_success {
            successes += 1;
            for i in 0..n_rules {
                fire_on_success[i] += trial_fires[i];
            }
        } else {
            for i in 0..n_rules {
                fire_on_failure[i] += trial_fires[i];
            }
        }

        costs.push(item.cost_spent);
        if trial_success {
            successful_costs.push(item.cost_spent);
        }
        total_steps += step as u64;
    }

    let fitness = compute_fitness(&successful_costs, &costs, successes, n_trials, total_steps);

    EvalResult {
        fitness,
        fire_on_success,
        fire_on_failure,
    }
}

fn compute_fitness(
    successful_costs: &[f32],
    all_costs: &[f32],
    successes: u32,
    n_trials: u32,
    total_steps: u64,
) -> Fitness {
    let success_rate = successes as f32 / n_trials as f32;

    let expected_cost = if successful_costs.is_empty() {
        f32::INFINITY
    } else {
        successful_costs.iter().sum::<f32>() / successful_costs.len() as f32
    };

    let (cost_median, cost_p90, cost_std) = if successful_costs.is_empty() {
        (f32::INFINITY, f32::INFINITY, 0.0)
    } else {
        let mut sorted = successful_costs.to_vec();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

        let median = sorted[sorted.len() / 2];
        let p90_idx = ((sorted.len() as f64) * 0.9) as usize;
        let p90 = sorted[p90_idx.min(sorted.len() - 1)];

        let mean = expected_cost;
        let variance = sorted.iter().map(|c| (c - mean).powi(2)).sum::<f32>()
            / sorted.len() as f32;
        let std = variance.sqrt();

        (median, p90, std)
    };

    let expected_steps = total_steps as f32 / n_trials as f32;
    let step_median = expected_steps; // approximation

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
/// Currently a placeholder — real implementation via batch.rs.
#[pyfunction]
pub fn evaluate_single() -> PyResult<()> {
    Ok(())
}
