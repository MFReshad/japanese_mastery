from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class ItemProgress(TimestampMixin, Base):
    __tablename__ = "item_progress"
    __table_args__ = (
        UniqueConstraint("item_type", "item_id", name="uq_progress_item"),
        CheckConstraint(
            "item_type in ('vocabulary', 'kanji')", name="ck_progress_item_type"
        ),
        CheckConstraint(
            "status in ('new', 'learning', 'weak', 'mastered')",
            name="ck_progress_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    current_correct_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(
        Float, default=0, server_default="0", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="new", server_default="new", nullable=False
    )
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_result: Mapped[Optional[str]] = mapped_column(String(20))
    last_practiced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint(
            "practice_type in ('vocabulary', 'kanji', 'mixed')",
            name="ck_session_practice_type",
        ),
        CheckConstraint(
            "mode in ('random', 'weak', 'wrong', 'never_practiced', 'mastery_review', 'starred', 'starred_priority')",
            name="ck_session_mode",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    practice_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    total_questions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    answers: Mapped[list["PracticeAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    questions: Mapped[list["PracticeQuestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PracticeQuestion(Base):
    __tablename__ = "practice_questions"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "position", name="uq_practice_question_position"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_entry_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(60), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer_primary: Mapped[str] = mapped_column(Text, nullable=False)
    answer_secondary: Mapped[Optional[str]] = mapped_column(Text)
    reveal_context: Mapped[Optional[dict]] = mapped_column(JSON)
    revealed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    session: Mapped[PracticeSession] = relationship(back_populates="questions")


class PracticeAnswer(Base):
    __tablename__ = "practice_answers"
    __table_args__ = (
        CheckConstraint(
            "item_type in ('vocabulary', 'kanji')", name="ck_answer_item_type"
        ),
        CheckConstraint("result in ('correct', 'wrong')", name="ck_answer_result"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("practice_questions.id", ondelete="SET NULL"), unique=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_entry_id: Mapped[Optional[int]] = mapped_column(Integer)
    question_type: Mapped[str] = mapped_column(String(60), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    wrong_note: Mapped[Optional[str]] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[PracticeSession] = relationship(back_populates="answers")


# Match the existing Alembic schema; do not invent additional indexes.
from sqlalchemy import Index, UniqueConstraint

Index(
    "ix_item_progress_type_item",
    ItemProgress.__table__.c["item_type"],
    ItemProgress.__table__.c["item_id"],
    unique=False,
)
Index(
    "ix_item_progress_type_status",
    ItemProgress.__table__.c["item_type"],
    ItemProgress.__table__.c["status"],
    unique=False,
)
Index(
    "ix_practice_questions_session_id",
    PracticeQuestion.__table__.c["session_id"],
    unique=False,
)
Index(
    "ix_practice_answers_item",
    PracticeAnswer.__table__.c["item_type"],
    PracticeAnswer.__table__.c["item_id"],
    unique=False,
)
