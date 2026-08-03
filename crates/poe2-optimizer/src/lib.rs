use pyo3::prelude::*;

mod item_state;
mod pool;
mod conditions;
mod actions;
mod evaluate;
mod batch;

/// Monte Carlo crafting simulation engine for the PoE2 optimizer.
/// Exposes evaluate_population() and evaluate_single() to Python via PyO3.
#[pymodule]
fn poe2_optimizer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(batch::evaluate_population, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate::evaluate_single, m)?)?;
    Ok(())
}
