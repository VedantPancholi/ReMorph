import sys
from types import ModuleType, SimpleNamespace

from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode
from sprint4.evaluation import reward_curve as reward_curve_module
from sprint4.training.trl_train_grpo import run_trl_training


def _install_fake_matplotlib(monkeypatch) -> None:
    pyplot = ModuleType("matplotlib.pyplot")

    class _Axis:
        def plot(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def set_title(self, *_args, **_kwargs):
            return None

        def set_xlabel(self, *_args, **_kwargs):
            return None

        def set_ylabel(self, *_args, **_kwargs):
            return None

        def grid(self, *_args, **_kwargs):
            return None

        def legend(self, *_args, **_kwargs):
            return None

    class _Figure:
        def add_subplot(self, *_args, **_kwargs):
            return _Axis()

        def tight_layout(self):
            return None

        def savefig(self, path, dpi=150):  # noqa: ARG002
            with open(path, "wb") as handle:
                handle.write(b"fake-png")

    pyplot.figure = lambda *args, **kwargs: _Figure()
    pyplot.close = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "matplotlib", ModuleType("matplotlib"))
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", pyplot)


def test_run_trl_training_writes_metrics_curve_and_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "trl", SimpleNamespace(__version__="0.test"))
    _install_fake_matplotlib(monkeypatch)

    benchmark_dir = tmp_path / "benchmark"
    run_benchmark_with_mode(
        bundle=load_contract_bundle(),
        episodes_per_scenario=1,
        output_dir=str(benchmark_dir),
        mode=BenchmarkRuntimeMode(
            cache_mode="clear",
            telemetry_enabled=False,
            cache_path=str(tmp_path / "repair_cache.json"),
            telemetry_dir=str(tmp_path / "telemetry"),
        ),
    )

    summary = run_trl_training(
        episodes_path=str(benchmark_dir / "episodes.jsonl"),
        output_dir=str(tmp_path / "training"),
        eval_ratio=0.34,
        seed=3,
    )

    assert summary["trainer"] == "hf_trl_structured_policy"
    assert summary["trl_version"] == "0.test"
    assert summary["status"] == "completed"
    assert (tmp_path / "training" / "trained_policy_model.json").exists()
    assert (tmp_path / "training" / "training_metrics.json").exists()
    assert (tmp_path / "training" / "reward_curve.json").exists()
    assert (tmp_path / "training" / "reward_curve.png").exists()
    assert (tmp_path / "training" / "warnings.json").exists()
    assert (tmp_path / "training" / "trained_policy_eval.json").exists()
    assert (tmp_path / "training" / "trained_policy_summary.json").exists()


def test_run_trl_training_still_writes_summary_without_matplotlib(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "trl", SimpleNamespace(__version__="0.test"))
    monkeypatch.setattr(
        reward_curve_module,
        "_plot_curve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(
                "matplotlib is required to export reward curves. Install it with "
                "'.venv/bin/pip install matplotlib'."
            )
        ),
    )

    benchmark_dir = tmp_path / "benchmark"
    run_benchmark_with_mode(
        bundle=load_contract_bundle(),
        episodes_per_scenario=1,
        output_dir=str(benchmark_dir),
        mode=BenchmarkRuntimeMode(
            cache_mode="clear",
            telemetry_enabled=False,
            cache_path=str(tmp_path / "repair_cache.json"),
            telemetry_dir=str(tmp_path / "telemetry"),
        ),
    )

    summary = run_trl_training(
        episodes_path=str(benchmark_dir / "episodes.jsonl"),
        output_dir=str(tmp_path / "training_no_plot"),
        eval_ratio=0.34,
        seed=3,
    )

    assert summary["status"] == "completed"
    assert summary["reward_curve"]["plot_generated"] is False
    assert summary["reward_curve"]["reward_curve_png"] == ""
    assert any("matplotlib is required" in warning for warning in summary["warnings"])
    assert (tmp_path / "training_no_plot" / "training_metrics.json").exists()
    assert (tmp_path / "training_no_plot" / "reward_curve.json").exists()
    assert not (tmp_path / "training_no_plot" / "reward_curve.png").exists()
    assert (tmp_path / "training_no_plot" / "trained_policy_summary.json").exists()
