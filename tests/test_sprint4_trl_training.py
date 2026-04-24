import sys
from types import ModuleType, SimpleNamespace

from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode
from sprint4.training.trl_train_grpo import run_trl_training


def test_run_trl_training_writes_dataset_and_eval_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "trl", SimpleNamespace(__version__="0.test"))

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

    assert summary["trainer"] == "trl_grpo"
    assert summary["trl_version"] == "0.test"
    assert summary["sample_count"] == 3
    assert summary["train_sample_count"] + summary["eval_sample_count"] == 3
    assert summary["eval_summary"]["sample_count"] == summary["eval_sample_count"]
    assert summary["training"]["status"] == "not_run"


def test_run_trl_training_executes_grpo_branch_with_fakes(tmp_path, monkeypatch) -> None:
    class _FakeGRPOConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeTrainer:
        def __init__(
            self,
            *,
            model,
            reward_funcs,
            args,
            train_dataset,
            eval_dataset,
            processing_class,
            **_,
        ) -> None:
            self.model = model
            self.reward_funcs = reward_funcs
            self.args = args
            self.train_dataset = train_dataset
            self.eval_dataset = eval_dataset
            self.processing_class = processing_class
            self.state = SimpleNamespace(global_step=1)

        def train(self):
            rewards = self.reward_funcs(
                completions=[item["target_completion"] for item in self.train_dataset.rows],
                target_completion=[item["target_completion"] for item in self.train_dataset.rows],
                reference_reward=[item["reference_reward"] for item in self.train_dataset.rows],
            )
            assert all(reward >= 1.0 for reward in rewards)
            return SimpleNamespace(metrics={"train_runtime": 0.1, "reward_mean": sum(rewards) / len(rewards)})

        def save_model(self, output_dir: str) -> None:
            __import__("pathlib").Path(output_dir).mkdir(parents=True, exist_ok=True)

    fake_trl = ModuleType("trl")
    fake_trl.__version__ = "0.fake"
    fake_trl.GRPOConfig = _FakeGRPOConfig
    fake_trl.GRPOTrainer = _FakeTrainer
    monkeypatch.setitem(sys.modules, "trl", fake_trl)

    class _FakeDataset:
        def __init__(self, rows) -> None:
            self.rows = rows

        @classmethod
        def from_list(cls, rows):
            return cls(rows)

    fake_datasets = ModuleType("datasets")
    fake_datasets.Dataset = _FakeDataset
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)

    class _FakeTokenizer:
        def __init__(self) -> None:
            self.pad_token_id = None
            self.eos_token = "</s>"
            self.pad_token = None

        def save_pretrained(self, output_dir: str) -> None:
            __import__("pathlib").Path(output_dir).mkdir(parents=True, exist_ok=True)

    class _FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(_model_name: str):
            return _FakeTokenizer()

    fake_transformers = ModuleType("transformers")
    fake_transformers.AutoTokenizer = _FakeAutoTokenizer
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

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
        model_name="fake-model",
        train_model=True,
        max_steps=1,
    )

    assert summary["trl_version"] == "0.fake"
    assert summary["training"]["status"] == "completed"
    assert summary["training"]["global_step"] == 1
    assert summary["training"]["config"]["max_steps"] == 1
