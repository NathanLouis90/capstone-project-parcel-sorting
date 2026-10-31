"""Bounded ACT action-chunk execution and temporal ensembling at inference time."""

from collections import deque
import math

import torch


class ACTActionSelector:
    """Select actions from chunks; positive ensemble coefficients favor older chunks.

    This follows the original ACT evaluation code's oldest-to-newest weighting
    order. Negative coefficients favor newer predictions. Zero gives equal weight.
    Predictions are tracked explicitly so legitimate zero actions remain valid.
    """

    def __init__(self, chunk_size, temporal_agg=False, coefficient=0.01, query_frequency=0):
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError('ACT chunk size must be a positive integer')
        if type(temporal_agg) is not bool:
            raise ValueError('ACT temporal ensembling must be true or false')
        if type(coefficient) not in (int, float) or not math.isfinite(coefficient):
            raise ValueError('ACT ensemble coefficient must be finite')
        if type(query_frequency) is not int or not 0 <= query_frequency <= chunk_size:
            raise ValueError('ACT replan interval must be 0 (full chunk) or between 1 and chunk length')
        self.chunk_size = chunk_size
        self.temporal_agg = temporal_agg
        self.coefficient = float(coefficient)
        self.query_frequency = 1 if temporal_agg else (query_frequency or chunk_size)
        self.reset()

    def reset(self):
        self.timestep = 0
        self.chunks = deque(maxlen=self.chunk_size)
        self.latest_chunk = None
        self.latest_start = None
        self.shape = None

    def select(self, predict):
        t = self.timestep
        while self.chunks and t - self.chunks[0][0] >= self.chunk_size:
            self.chunks.popleft()
        if t % self.query_frequency == 0:
            prediction = predict()
            if (not isinstance(prediction, torch.Tensor) or not prediction.is_floating_point()
                    or prediction.ndim != 3 or prediction.shape[0] < 1 or prediction.shape[2] < 1
                    or prediction.shape[1] != self.chunk_size or not torch.isfinite(prediction).all()):
                raise ValueError('ACT must predict finite (batch, chunk length, actions) tensors')
            shape = (prediction.shape[0], prediction.shape[2])
            if self.shape is not None and shape != self.shape:
                raise ValueError('ACT prediction batch/action dimensions changed within an episode')
            self.shape = shape
            self.latest_chunk, self.latest_start = prediction.detach(), t
            if self.temporal_agg:
                self.chunks.append((t, self.latest_chunk))
        if self.temporal_agg:
            candidates = torch.stack([chunk[:, t - start, :] for start, chunk in self.chunks])
            order = torch.arange(len(self.chunks), dtype=torch.float64, device=candidates.device)
            # Anchor the maximum log weight at zero to avoid exponential overflow.
            anchor = order[0] if self.coefficient >= 0 else order[-1]
            weights = torch.softmax(-self.coefficient * (order - anchor), dim=0).to(candidates.dtype)
            action = (candidates * weights[:, None, None]).sum(dim=0)
        else:
            action = self.latest_chunk[:, t - self.latest_start, :]
        self.timestep += 1
        return action
