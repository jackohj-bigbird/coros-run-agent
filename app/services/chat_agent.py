from datetime import date

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import TrainingPlanItem
from app.services.analysis import build_weekly_summary, format_pace


SYSTEM_PROMPT = """
你是跑步教练AI，目标是帮助用户在2026-05-01完成半马并冲击1:40。
用户每周最多跑4天，通常在周二、周四、周六、周日。
回答要求：
1) 先给结论，再给依据。
2) 训练建议具体到下一次训练。
3) 若负荷过高，优先建议恢复。
4) 语言简洁，中文输出。
""".strip()


class ChatAgent:
    def __init__(self) -> None:
        self.model = settings.openai_model

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def _build_context(self, db: Session) -> str:
        summary = build_weekly_summary(db, anchor=date.today())
        upcoming = db.scalars(
            select(TrainingPlanItem)
            .where(TrainingPlanItem.plan_date >= date.today())
            .order_by(TrainingPlanItem.plan_date.asc())
            .limit(5)
        ).all()

        lines = [
            f"本周区间: {summary.week_start} 到 {summary.week_end}",
            f"本周跑步次数: {summary.run_count}",
            f"本周总里程: {summary.total_distance_km} km",
            f"本周总时长: {summary.total_time_min} min",
            f"本周平均配速: {format_pace(summary.avg_pace_min_per_km)}",
            f"本周最长距离: {summary.longest_run_km} km",
            f"本周计划完成率: {int(summary.completion_rate * 100)}%",
            "未来5次计划:",
        ]
        for item in upcoming:
            lines.append(
                f"- {item.plan_date} {item.session_type} {item.planned_distance_km}km 配速{item.target_pace_min_per_km}"
            )
        return "\n".join(lines)

    def ask(self, db: Session, question: str) -> str:
        context = self._build_context(db)

        if not self.is_configured():
            return (
                "已收到问题，但当前未配置 OPENAI_API_KEY。"
                "你可以先问我固定模板问题，我会基于规则回答；"
                "要启用自然对话，请在 .env 填入 OPENAI_API_KEY。\n\n"
                f"当前训练上下文：\n{context}"
            )

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"训练数据:\n{context}\n\n问题: {question}"},
            ],
        )
        return response.choices[0].message.content or "未生成回复。"
