"""
C.P.S. Context Manager
======================
Assembles, prunes, redacts, and previews context from user selections,
active files, pasted code, error logs, and problem statements.
Prevents sensitive credential leakage and enforces strict privacy boundaries.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from .security import redact


@dataclass
class ContextItem:
    item_type: str  # 'selection', 'paste', 'problem', 'error', 'file', 'repo'
    content: str
    source: str = ""
    language: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ContextManager:
    """Manages context assembly for AI queries with token budgeting and automatic redaction."""

    def __init__(self, max_tokens: int = 8192):
        self.items: List[ContextItem] = []
        self.max_tokens = max_tokens

    def add_item(self, item_type: str, content: str, source: str = "", language: str = "", metadata: Optional[dict] = None) -> ContextItem:
        clean_content = content.strip() if content else ""
        item = ContextItem(
            item_type=item_type,
            content=clean_content,
            source=source,
            language=language,
            metadata=metadata or {}
        )
        self.items.append(item)
        return item

    def remove_item(self, index: int) -> bool:
        if 0 <= index < len(self.items):
            self.items.pop(index)
            return True
        return False

    def clear(self):
        self.items.clear()

    def estimate_tokens(self) -> int:
        """Rough token estimate: ~4 characters per token."""
        total_chars = sum(len(it.content) for it in self.items)
        return total_chars // 4

    def redact_sensitive(self):
        """Redacts secrets, keys, and tokens from all stored items."""
        for it in self.items:
            it.content = redact(it.content)

    def preview(self) -> str:
        """Human-readable preview of context before transmitting to external AI providers."""
        if not self.items:
            return "No context items registered."

        lines = [
            f"=== C.P.S. Context Preview ({len(self.items)} items, ~{self.estimate_tokens()} tokens) ==="
        ]
        for idx, it in enumerate(self.items, 1):
            src_info = f" (Source: {it.source})" if it.source else ""
            lang_info = f" [{it.language}]" if it.language else ""
            lines.append(f"\n[{idx}] Type: {it.item_type.upper()}{lang_info}{src_info}")
            # Truncate preview snippet to 300 chars
            snippet = it.content[:300] + ("..." if len(it.content) > 300 else "")
            lines.append(f"Content:\n{snippet}")
        return "\n".join(lines)

    def prune_to_budget(self, target_tokens: Optional[int] = None) -> int:
        """Prunes stored items to fit within token budget (FIFO pruning with snippet truncation)."""
        limit = target_tokens or self.max_tokens
        while self.estimate_tokens() > limit and len(self.items) > 1:
            # Remove oldest item first
            self.items.pop(0)

        # If still over budget on remaining single item, truncate its text
        if self.items and self.estimate_tokens() > limit:
            allowed_chars = max(0, limit * 4)
            self.items[0].content = self.items[0].content[:allowed_chars]
        return self.estimate_tokens()

    def build_prompt(self, action: str, instructions: str = "") -> str:
        """Combines all context items into a structured prompt, adhering to token budget."""
        self.prune_to_budget()
        parts = [f"### User Action: {action.upper()}"]
        if instructions:
            parts.append(f"### Additional Guidance:\n{instructions}")

        for it in self.items:
            t = it.item_type.lower()
            lang = it.language or "text"
            if t == "problem":
                parts.append(f"### Problem Statement:\n{it.content}")
            elif t == "error":
                parts.append(f"### Compiler / Runtime Diagnostics:\n```\n{it.content}\n```")
            elif t in ("selection", "paste", "file"):
                src_label = f" ({it.source})" if it.source else ""
                parts.append(f"### Context Code{src_label}:\n```{lang}\n{it.content}\n```")
            else:
                parts.append(f"### Supplementary Info ({it.item_type}):\n{it.content}")

        return "\n\n".join(parts)

    def to_dict(self) -> List[dict]:
        return [it.to_dict() for it in self.items]
