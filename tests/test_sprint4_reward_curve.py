import json
import sys
from types import ModuleType

from sprint4.evaluation.reward_curve import export_reward_curve


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


def test_export_reward_curve_writes_json_and_png(tmp_path, monkeypatch) -> None:
    _install_fake_matplotlib(monkeypatch)
    metrics_path = tmp_path / "training_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "metrics": [
                    {"step": 1, "epoch": 1, "train_reward": 0.5, "eval_reward": 0.4},
                    {"step": 2, "epoch": 2, "train_reward": 0.8, "eval_reward": 0.6},
                ]
            }
        ),
        encoding="utf-8",
    )

    artifacts = export_reward_curve(metrics_path=str(metrics_path), output_dir=str(tmp_path))

    assert artifacts["reward_curve_json"].endswith("reward_curve.json")
    assert artifacts["reward_curve_png"].endswith("reward_curve.png")
    assert (tmp_path / "reward_curve.json").exists()
    assert (tmp_path / "reward_curve.png").exists()
