from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..context import Context


def get_ctx(request: Request) -> Context:
    return request.app.state.ctx


CtxDep = Annotated[Context, Depends(get_ctx)]
