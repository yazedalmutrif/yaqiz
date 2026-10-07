"""Print the torch / CUDA / Ultralytics versions and run a small GPU matmul."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import PROJECT_NAME  # noqa: E402


def main() -> int:
    import torch
    import ultralytics

    print(f"{PROJECT_NAME} environment check")
    print(f"python       {sys.version.split()[0]}")
    print(f"torch        {torch.__version__}  (CUDA build {torch.version.cuda})")
    print(f"ultralytics  {ultralytics.__version__}")
    ok = torch.cuda.is_available()
    print(f"cuda ok      {ok}")
    if not ok:
        return 1
    print(f"gpu          {torch.cuda.get_device_name(0)}")
    print(f"cudnn        {torch.backends.cudnn.version()}")
    x = torch.randn(4096, 4096, device="cuda")
    torch.cuda.synchronize()
    y = (x @ x).sum().item()
    print(f"matmul       ok ({y:.3e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
