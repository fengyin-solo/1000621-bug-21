"""检测项目业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "project"
REQUIRED_FIELDS = ["项目编码", "项目名称", "检测方法"]
STATUS_ORDER = ["草稿", "已启用", "待修订", "已停用"]
ACTION_RULES = {"启用项目": "已启用", "提交修订": "待修订", "停用项目": "已停用"}
NEGATIVE_ACTIONS = ["停用项目"]

FILTERABLE_FIELDS = ["项目编码", "项目名称", "检测方法"]
DISABLED_STATUS = "已停用"
PRICE_FIELD = "收费单价"


def _price_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    """收费单价从高到低排；不是数字的一律沉底，再按项目编码稳住先后。"""
    raw = str(row.get(PRICE_FIELD) or "").strip()
    try:
        return (0, -float(raw), str(row.get("项目编码", "")))
    except ValueError:
        return (1, 0.0, str(row.get("项目编码", "")))


class ProjectService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        filters: dict[str, str | None] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # 已停用项目不进可选结果；列表与导出共用这一套口径，保证两边一致。
        rows = [row for row in store.rows(MODULE) if row.get("status") != DISABLED_STATUS]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("项目编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        for field, value in (filters or {}).items():
            if field in FILTERABLE_FIELDS and value:
                rows = [row for row in rows if value in str(row.get(field, ""))]
        rows = sorted(rows, key=_price_sort_key)
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
