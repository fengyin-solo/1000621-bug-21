"""检测项目业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "project"
REQUIRED_FIELDS = ["项目编码", "项目名称", "检测方法"]
STATUS_ORDER = ["草稿", "已启用", "待修订", "已停用"]
ACTION_RULES = {"启用项目": "已启用", "提交修订": "待修订", "停用项目": "已停用"}
NEGATIVE_ACTIONS = ["停用项目"]
# 已停用项目不进入列表与导出等可选结果，只能由启用项目动作重新带回
HIDDEN_STATUSES = {"已停用"}


def _sort_by_price(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """收费单价按数值从高到低排；缺失或非数值的沉底，用 id 兜底保证次序稳定。"""

    def key(row: dict[str, Any]) -> tuple[int, float, int]:
        try:
            price = float(str(row.get("收费单价") or "").strip())
        except ValueError:
            return (1, 0.0, int(row.get("id", 0)))
        return (0, -price, int(row.get("id", 0)))

    return sorted(rows, key=key)


class ProjectService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        method: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [row for row in store.rows(MODULE) if row.get("status") not in HIDDEN_STATUSES]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("项目编码", ""))]
        if name:
            rows = [row for row in rows if name in str(row.get("项目名称", ""))]
        if method:
            rows = [row for row in rows if method in str(row.get("检测方法", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows = _sort_by_price(rows)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测项目 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检测项目可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"检测项目已{action}"
