# ACT model backend

Source: https://github.com/tonyzhaozh/act, branch `robomimic`.
Revision: `20fc6e990698534b89a41c2c85f54b7ff4b0c280`.

Only the DETR model sources are included. The ACT MIT license is retained in LICENSE, and the DETR Apache-2.0 license is retained in act/detr/LICENSE.
Local changes: model construction accepts device and pretrained-backbone flags,
so offline CPU smoke tests do not require CUDA or pretrained-weight downloads.
This backend is distinct from Dobot's immutable vendor bytecode.
