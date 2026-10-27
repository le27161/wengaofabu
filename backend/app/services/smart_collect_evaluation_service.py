# -*- coding: utf-8 -*-
"""智能采编相关性评估：只读统计、同任务排序一致率和异常样本。"""
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models.smart_collect import NewsClue, SmartCollectTask, SmartCollectTaskClue
from ..models.user import User


class SmartCollectEvaluationService:
    """仅评估已有人工标签，不搜索、不推理，也不写数据库。"""

    @staticmethod
    def _visible_labeled_rows(db: Session, user: User):
        query = (
            db.query(
                SmartCollectTaskClue.task_id.label("task_id"),
                SmartCollectTaskClue.clue_id.label("clue_id"),
                SmartCollectTaskClue.relevance_label.label("relevance_label"),
                SmartCollectTaskClue.search_score.label("search_score"),
                SmartCollectTaskClue.semantic_score.label("semantic_score"),
            )
            .join(SmartCollectTask, SmartCollectTask.id == SmartCollectTaskClue.task_id)
            .filter(SmartCollectTaskClue.relevance_label.isnot(None))
        )
        if user.role != "admin":
            query = query.filter(SmartCollectTask.creator_id == user.id)
        return query.order_by(SmartCollectTaskClue.task_id, SmartCollectTaskClue.clue_id).all()

    @staticmethod
    def _score_stats(values: list[float]) -> dict:
        if not values:
            return {
                "count": 0,
                "average": None,
                "minimum": None,
                "maximum": None,
            }
        return {
            "count": len(values),
            "average": sum(values) / len(values),
            "minimum": min(values),
            "maximum": max(values),
        }

    @classmethod
    def _ranking_agreement(cls, rows: list, score_name: str) -> dict:
        """同任务内每个不同标签pair只比较一次；同分计tie并排除出rate。"""
        rows_by_task = defaultdict(list)
        for row in rows:
            rows_by_task[row.task_id].append(row)

        correct = 0
        incorrect = 0
        ties = 0
        for task_rows in rows_by_task.values():
            for left_index, left in enumerate(task_rows):
                for right in task_rows[left_index + 1:]:
                    if left.relevance_label == right.relevance_label:
                        continue
                    left_score = getattr(left, score_name)
                    right_score = getattr(right, score_name)
                    if left_score is None or right_score is None:
                        continue

                    label_direction = 1 if left.relevance_label > right.relevance_label else -1
                    if left_score == right_score:
                        ties += 1
                        continue
                    score_direction = 1 if left_score > right_score else -1
                    if score_direction == label_direction:
                        correct += 1
                    else:
                        incorrect += 1

        total = correct + incorrect
        return {
            "correct": correct,
            "incorrect": incorrect,
            "ties": ties,
            "total": total,
            "rate": correct / total if total else None,
        }

    @classmethod
    def get_summary(cls, db: Session, user: User) -> dict:
        """汇总当前用户有权查看任务中的全部已标注线索。"""
        rows = cls._visible_labeled_rows(db, user)
        label_counts = {0: 0, 1: 0, 2: 0}
        search_values = {0: [], 1: [], 2: []}
        semantic_values = {0: [], 1: [], 2: []}
        semantic_null_counts = {0: 0, 1: 0, 2: 0}

        for row in rows:
            label = row.relevance_label
            label_counts[label] += 1
            search_values[label].append(float(row.search_score))
            if row.semantic_score is None:
                semantic_null_counts[label] += 1
            else:
                semantic_values[label].append(float(row.semantic_score))

        search_stats = {
            label: cls._score_stats(search_values[label])
            for label in (0, 1, 2)
        }
        semantic_stats = {}
        for label in (0, 1, 2):
            semantic_stats[label] = {
                **cls._score_stats(semantic_values[label]),
                "null_count": semantic_null_counts[label],
            }

        return {
            "total_labeled": len(rows),
            "label_counts": {str(label): label_counts[label] for label in (0, 1, 2)},
            "search_score_stats": {str(label): search_stats[label] for label in (0, 1, 2)},
            "semantic_score_stats": {
                str(label): semantic_stats[label] for label in (0, 1, 2)
            },
            "ranking_agreement": {
                "search_score": cls._ranking_agreement(rows, "search_score"),
                "semantic_score": cls._ranking_agreement(rows, "semantic_score"),
            },
        }

    @staticmethod
    def _outlier_rows(
        db: Session,
        user: User,
        relevance_label: int,
        score_name: str,
        descending: bool,
        limit: int,
    ) -> list[dict]:
        score_column = getattr(SmartCollectTaskClue, score_name)
        query = (
            db.query(
                SmartCollectTask.id.label("task_id"),
                SmartCollectTask.query.label("query"),
                SmartCollectTaskClue.clue_id.label("clue_id"),
                SmartCollectTaskClue.rank.label("rank"),
                NewsClue.title.label("title"),
                NewsClue.source.label("source"),
                SmartCollectTaskClue.search_score.label("search_score"),
                SmartCollectTaskClue.semantic_score.label("semantic_score"),
                SmartCollectTaskClue.relevance_label.label("relevance_label"),
            )
            .join(SmartCollectTask, SmartCollectTask.id == SmartCollectTaskClue.task_id)
            .join(NewsClue, NewsClue.id == SmartCollectTaskClue.clue_id)
            .filter(SmartCollectTaskClue.relevance_label == relevance_label)
        )
        if score_name == "semantic_score":
            query = query.filter(SmartCollectTaskClue.semantic_score.isnot(None))
        if user.role != "admin":
            query = query.filter(SmartCollectTask.creator_id == user.id)

        score_order = score_column.desc() if descending else score_column.asc()
        rows = (
            query.order_by(
                score_order,
                SmartCollectTask.id.asc(),
                SmartCollectTaskClue.rank.asc(),
                SmartCollectTaskClue.clue_id.asc(),
            )
            .limit(limit)
            .all()
        )
        return [dict(row._mapping) for row in rows]

    @classmethod
    def get_outliers(cls, db: Session, user: User, limit: int = 5) -> dict:
        """按单项原始分数找人工标签两端的偏差样本，不计算混合分数。"""
        if not 1 <= limit <= 20:
            raise ValueError("limit必须在1到20之间")
        return {
            "semantic_label_0_high": cls._outlier_rows(
                db, user, 0, "semantic_score", True, limit
            ),
            "semantic_label_2_low": cls._outlier_rows(
                db, user, 2, "semantic_score", False, limit
            ),
            "search_label_0_high": cls._outlier_rows(
                db, user, 0, "search_score", True, limit
            ),
            "search_label_2_low": cls._outlier_rows(
                db, user, 2, "search_score", False, limit
            ),
        }
