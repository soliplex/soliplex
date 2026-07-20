import dataclasses
import re
import typing

from pydantic_ai import RunContext
from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import messages as ai_messages
from pydantic_ai import tools as ai_tools

from soliplex import loggers

_CHUNK_REF = re.compile(r"^\[([^\]]+)\] \[rank", re.MULTILINE)


def _result_refs(result: typing.Any) -> list[str]:
    if isinstance(result, ai_messages.ToolReturn):
        result = result.return_value
    return _CHUNK_REF.findall(str(result))


@dataclasses.dataclass
class RAGAccessAuditCapability(ai_capabilities.AbstractCapability[typing.Any]):
    """Audit native RAG capability tools without observing AG-UI events."""

    db_paths: dict[str, str]

    def _audit_log(self, ctx: RunContext[typing.Any]):
        deps = ctx.deps
        user = getattr(deps, "user", None)
        return loggers.RAGAccessAuditLog(
            claims=user.model_dump() if user is not None else {},
            room_id=getattr(deps, "room_id", None),
            thread_id=getattr(deps, "thread_id", None),
            run_id=getattr(deps, "run_id", None),
        )

    async def after_tool_execute(
        self,
        ctx: RunContext[typing.Any],
        *,
        call: ai_messages.ToolCallPart,
        tool_def: ai_tools.ToolDefinition,
        args: dict[str, typing.Any],
        result: typing.Any,
    ) -> typing.Any:
        capability_id = tool_def.capability_id
        db_path = self.db_paths.get(capability_id or "")
        if db_path is not None:
            self._audit_log(ctx).retrieval(
                db_path,
                tool_def.name,
                args,
                _result_refs(result),
            )
        return result

    async def on_tool_execute_error(
        self,
        ctx: RunContext[typing.Any],
        *,
        call: ai_messages.ToolCallPart,
        tool_def: ai_tools.ToolDefinition,
        args: dict[str, typing.Any],
        error: Exception,
    ) -> typing.Any:
        capability_id = tool_def.capability_id
        db_path = self.db_paths.get(capability_id or "")
        if db_path is not None:
            self._audit_log(ctx).retrieval_failed(
                db_path,
                tool_def.name,
                args,
                type(error).__name__,
            )
        raise error


__all__ = ["RAGAccessAuditCapability"]
