from __future__ import annotations

import numpy as np
import torch


def resolve_runtime_device(device: str | None = None) -> str:
    if device is not None and str(device).lower().startswith("cuda"):
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class TorchPrimeKGIndicationRanker(torch.nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_layer_sizes: tuple[int, int] = (128, 32),
        device: str | None = None,
    ) -> None:
        super().__init__()
        self.input_dim = int(input_dim)
        self.hidden_layer_sizes = tuple(int(value) for value in hidden_layer_sizes)
        self.device = resolve_runtime_device(device)
        hidden_1, hidden_2 = self.hidden_layer_sizes
        self.network = torch.nn.Sequential(
            torch.nn.Linear(self.input_dim, hidden_1),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_1, hidden_2),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_2, 1),
        )
        self.constant_logit: float | None = None
        self.to(self.device)

    def to(self, device: str | None):  # type: ignore[override]
        self.device = resolve_runtime_device(device)
        return super().to(self.device)

    def forward(self, pair_matrix) -> torch.Tensor:
        if not isinstance(pair_matrix, torch.Tensor):
            pair_matrix = torch.as_tensor(pair_matrix, dtype=torch.float32, device=self.device)
        else:
            pair_matrix = pair_matrix.to(self.device, dtype=torch.float32)
        if pair_matrix.ndim != 2 or pair_matrix.shape[1] != self.input_dim:
            raise ValueError(
                f"Expected pair matrix with shape (n, {self.input_dim}), got {tuple(pair_matrix.shape)}."
            )
        if self.constant_logit is not None:
            return torch.full((pair_matrix.shape[0],), self.constant_logit, dtype=torch.float32, device=self.device)
        return self.network(pair_matrix).squeeze(-1)

    def predict_scores(self, pair_matrix) -> np.ndarray:
        self.eval()
        with torch.no_grad():
            logits = self.forward(pair_matrix)
            return torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32)

    def export_state(self) -> dict:
        return {
            "input_dim": self.input_dim,
            "hidden_layer_sizes": list(self.hidden_layer_sizes),
            "device": self.device,
            "constant_logit": self.constant_logit,
            "state_dict": self.state_dict(),
        }

    @classmethod
    def from_state(cls, payload: dict, device: str | None = None) -> "TorchPrimeKGIndicationRanker":
        target_device = resolve_runtime_device(device if device is not None else payload.get("device"))
        model = cls(
            input_dim=payload["input_dim"],
            hidden_layer_sizes=tuple(payload["hidden_layer_sizes"]),
            device=target_device,
        )
        model.load_state_dict(payload["state_dict"])
        model.constant_logit = payload.get("constant_logit")
        model.to(target_device)
        model.eval()
        return model
