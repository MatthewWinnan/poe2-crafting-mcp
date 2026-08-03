/// Batch evaluation of entire population via rayon parallelism.
/// This is the main entry point called from Python each generation.

use numpy::{PyArray2, PyReadonlyArray1, PyReadonlyArray3, IntoPyArray};
use ndarray::Array2;
use pyo3::prelude::*;
use rayon::prelude::*;

use crate::evaluate::{evaluate_rulelist, Rule};
use crate::pool::ModPool;

/// Evaluate entire population in parallel.
///
/// Args:
///   rules_array: (pop_size, max_rules, 5) u16 — [predicate, arg1, arg2, currency, omen]
///   rule_counts: (pop_size,) u8 — actual rule count per individual
///   prefix_weights: (n_prefix,) u32 — prefix mod weights
///   prefix_cumsum: (n_prefix,) u64 — prefix cumulative sums
///   prefix_families: (n_prefix,) u16
///   prefix_tiers: (n_prefix,) u8
///   prefix_req_levels: (n_prefix,) u8
///   suffix_weights: (n_suffix,) u32
///   suffix_cumsum: (n_suffix,) u64
///   suffix_families: (n_suffix,) u16
///   suffix_tiers: (n_suffix,) u8
///   suffix_req_levels: (n_suffix,) u8
///   target_prefix_families: (n_tp,) u16
///   target_suffix_families: (n_ts,) u16
///   target_max_tiers: (n_targets,) u8
///   prices: (n_prices,) f32 — [currency_prices..., omen_prices...]
///   max_currency_id: u16
///   ilvl: u8
///   max_prefixes: u8
///   max_suffixes: u8
///   n_trials: u32
///   max_steps: u32
///   base_seed: u64
///
/// Returns: (fitness_array, fire_success_array, fire_failure_array)
///   fitness_array: (pop_size, 7) f32 — [cost, success_rate, p90, median, std, steps, step_med]
///   fire_success_array: (pop_size, max_rules) u32
///   fire_failure_array: (pop_size, max_rules) u32
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn evaluate_population<'py>(
    py: Python<'py>,
    rules_array: PyReadonlyArray3<'py, u16>,
    rule_counts: PyReadonlyArray1<'py, u8>,
    prefix_weights: PyReadonlyArray1<'py, u32>,
    prefix_cumsum: PyReadonlyArray1<'py, u64>,
    prefix_families: PyReadonlyArray1<'py, u16>,
    prefix_tiers: PyReadonlyArray1<'py, u8>,
    prefix_req_levels: PyReadonlyArray1<'py, u8>,
    suffix_weights: PyReadonlyArray1<'py, u32>,
    suffix_cumsum: PyReadonlyArray1<'py, u64>,
    suffix_families: PyReadonlyArray1<'py, u16>,
    suffix_tiers: PyReadonlyArray1<'py, u8>,
    suffix_req_levels: PyReadonlyArray1<'py, u8>,
    target_prefix_families: PyReadonlyArray1<'py, u16>,
    target_suffix_families: PyReadonlyArray1<'py, u16>,
    target_max_tiers: PyReadonlyArray1<'py, u8>,
    prices: PyReadonlyArray1<'py, f32>,
    max_currency_id: u16,
    ilvl: u8,
    max_prefixes: u8,
    max_suffixes: u8,
    n_trials: u32,
    max_steps: u32,
    base_seed: u64,
) -> PyResult<(
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<u32>>,
    Bound<'py, PyArray2<u32>>,
)> {
    // Extract numpy arrays to Rust vecs (one-time copy at boundary)
    let rules_arr = rules_array.as_array();
    let rule_counts_arr = rule_counts.as_array();
    let pop_size = rule_counts_arr.len();
    let max_rules = rules_arr.shape()[1];

    // Build the shared ModPool (read-only, shared across all threads)
    let pool = ModPool {
        prefix_weights: prefix_weights.as_array().to_vec(),
        prefix_cumsum: prefix_cumsum.as_array().to_vec(),
        prefix_families: prefix_families.as_array().to_vec(),
        prefix_tiers: prefix_tiers.as_array().to_vec(),
        prefix_req_levels: prefix_req_levels.as_array().to_vec(),
        prefix_total_weight: prefix_cumsum.as_array().last().copied().unwrap_or(0),
        suffix_weights: suffix_weights.as_array().to_vec(),
        suffix_cumsum: suffix_cumsum.as_array().to_vec(),
        suffix_families: suffix_families.as_array().to_vec(),
        suffix_tiers: suffix_tiers.as_array().to_vec(),
        suffix_req_levels: suffix_req_levels.as_array().to_vec(),
        suffix_total_weight: suffix_cumsum.as_array().last().copied().unwrap_or(0),
        target_prefix_families: target_prefix_families.as_array().to_vec(),
        target_suffix_families: target_suffix_families.as_array().to_vec(),
        target_max_tiers: target_max_tiers.as_array().to_vec(),
        all_target_families: {
            let mut all = target_prefix_families.as_array().to_vec();
            all.extend(target_suffix_families.as_array().iter());
            all
        },
        ilvl,
        max_prefixes,
        max_suffixes,
    };

    let prices_vec: Vec<f32> = prices.as_array().to_vec();
    let max_cid = max_currency_id as usize;

    // Pre-extract rules for each individual (avoid repeated numpy indexing in parallel)
    let mut all_rules: Vec<Vec<Rule>> = Vec::with_capacity(pop_size);
    let mut all_counts: Vec<usize> = Vec::with_capacity(pop_size);

    for i in 0..pop_size {
        let n = rule_counts_arr[i] as usize;
        all_counts.push(n);
        let mut rules = Vec::with_capacity(n);
        for j in 0..n {
            rules.push(Rule {
                predicate: rules_arr[[i, j, 0]],
                arg1: rules_arr[[i, j, 1]],
                arg2: rules_arr[[i, j, 2]],
                currency: rules_arr[[i, j, 3]],
                omen: rules_arr[[i, j, 4]],
            });
        }
        all_rules.push(rules);
    }

    // Release GIL and evaluate in parallel
    let results: Vec<_> = py.allow_threads(|| {
        (0..pop_size)
            .into_par_iter()
            .map(|i| {
                let seed = base_seed.wrapping_add(i as u64 * 7919);
                evaluate_rulelist(
                    &all_rules[i],
                    all_counts[i],
                    &pool,
                    &prices_vec,
                    max_cid,
                    n_trials,
                    max_steps,
                    seed,
                )
            })
            .collect::<Vec<_>>()
    });

    // Pack results into ndarray for zero-copy return to Python
    let mut fitness_nd = Array2::<f32>::zeros((pop_size, 7));
    let mut fire_success_nd = Array2::<u32>::zeros((pop_size, max_rules));
    let mut fire_failure_nd = Array2::<u32>::zeros((pop_size, max_rules));

    for (i, result) in results.iter().enumerate() {
        fitness_nd[[i, 0]] = result.fitness.expected_cost;
        fitness_nd[[i, 1]] = result.fitness.success_rate;
        fitness_nd[[i, 2]] = result.fitness.cost_p90;
        fitness_nd[[i, 3]] = result.fitness.cost_median;
        fitness_nd[[i, 4]] = result.fitness.cost_std;
        fitness_nd[[i, 5]] = result.fitness.expected_steps;
        fitness_nd[[i, 6]] = result.fitness.step_median;

        for j in 0..all_counts[i].min(max_rules) {
            fire_success_nd[[i, j]] = result.fire_on_success[j];
            fire_failure_nd[[i, j]] = result.fire_on_failure[j];
        }
    }

    // Convert to numpy arrays
    let fitness_array = fitness_nd.into_pyarray_bound(py);
    let fire_success_array = fire_success_nd.into_pyarray_bound(py);
    let fire_failure_array = fire_failure_nd.into_pyarray_bound(py);

    Ok((fitness_array, fire_success_array, fire_failure_array))
}
