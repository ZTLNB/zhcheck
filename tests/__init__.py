"""测试包初始化：把 src 与 tests 目录加入 sys.path，使测试无需安装即可运行。

运行方式（在项目根目录）：

    python -m unittest discover -v
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _candidate in (str(_HERE), str(_HERE.parent / "src")):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)
