"""
SQLAlchemy domain models for the AG Cloud platform.

Pattern: BaseModel with IdMixin + TimestampMixin (same as nus project).
Models: AgentConfig, TaskLog, LLMTokenUsage
"""

import logging
from datetime import datetime, date
from typing import Any, Dict

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    inspect as sqlalchemy_inspect
)
from sqlalchemy.orm import Mapped, mapped_column
from .util_database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        "CreatedAt",
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        "UpdatedAt",
        DateTime,
        nullable=True,
        onupdate=datetime.utcnow,
    )


class IdMixin:
    id: Mapped[int] = mapped_column(
        "Id",
        Integer,
        primary_key=True,
        autoincrement=True,
    )


class BaseModel(Base, IdMixin, TimestampMixin):
    __abstract__ = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dict using SQLAlchemy mapper."""
        mapper = sqlalchemy_inspect(self.__class__)
        d: Dict[str, Any] = {}
        for attr in mapper.attrs:
            if not hasattr(attr, 'columns') or len(attr.columns) == 0:
                continue
            sql_name = attr.columns[0].name
            python_attr = attr.key
            value = getattr(self, python_attr)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            d[sql_name] = value
        return d


class AgentConfig(BaseModel):
    """Configuration for registered agents."""
    __tablename__ = "AgentConfig"

    __upsert_keys__ = ["agent_type"]

    __create_sql__ = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AgentConfig' AND xtype='U')
    CREATE TABLE AgentConfig (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        AgentType NVARCHAR(50) NOT NULL,
        DisplayName NVARCHAR(100) NOT NULL,
        Description NVARCHAR(500),
        SystemPromptPath NVARCHAR(200),
        ModelDeployment NVARCHAR(100),
        IsEnabled BIT NOT NULL DEFAULT 1,
        MaxTokens INT DEFAULT 4096,
        Temperature FLOAT DEFAULT 0.7,
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME,
        CONSTRAINT UQ_AgentConfig UNIQUE (AgentType)
    )
    """

    agent_type: Mapped[str] = mapped_column(
        "AgentType", String(50), nullable=False
    )
    display_name: Mapped[str] = mapped_column(
        "DisplayName", String(100), nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        "Description", String(500), nullable=True
    )
    system_prompt_path: Mapped[str | None] = mapped_column(
        "SystemPromptPath", String(200), nullable=True
    )
    model_deployment: Mapped[str | None] = mapped_column(
        "ModelDeployment", String(100), nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(
        "IsEnabled", Integer, nullable=False, default=1
    )
    max_tokens: Mapped[int | None] = mapped_column(
        "MaxTokens", Integer, nullable=True, default=4096
    )
    temperature: Mapped[float | None] = mapped_column(
        "Temperature", String(10), nullable=True, default="0.7"
    )

    def __repr__(self) -> str:
        return f"<AgentConfig type={self.agent_type!r} enabled={self.is_enabled}>"


class TaskLog(BaseModel):
    """Log of agent task executions."""
    __tablename__ = "TaskLog"

    __upsert_keys__ = ["task_id"]

    __create_sql__ = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TaskLog' AND xtype='U')
    CREATE TABLE TaskLog (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        TaskId NVARCHAR(100) NOT NULL,
        AgentType NVARCHAR(50) NOT NULL,
        EventType NVARCHAR(50),
        Status NVARCHAR(20) NOT NULL DEFAULT 'pending',
        InputPayload NVARCHAR(MAX),
        OutputPayload NVARCHAR(MAX),
        ErrorMessage NVARCHAR(MAX),
        StartedAt DATETIME,
        CompletedAt DATETIME,
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME,
        CONSTRAINT UQ_TaskLog UNIQUE (TaskId)
    )
    """

    task_id: Mapped[str] = mapped_column(
        "TaskId", String(100), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(
        "AgentType", String(50), nullable=False
    )
    event_type: Mapped[str | None] = mapped_column(
        "EventType", String(50), nullable=True
    )
    status: Mapped[str] = mapped_column(
        "Status", String(20), nullable=False, default="pending"
    )
    input_payload: Mapped[str | None] = mapped_column(
        "InputPayload", String(4000), nullable=True
    )
    output_payload: Mapped[str | None] = mapped_column(
        "OutputPayload", String(4000), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        "ErrorMessage", String(4000), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        "StartedAt", DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        "CompletedAt", DateTime, nullable=True
    )

    def __repr__(self) -> str:
        return f"<TaskLog task={self.task_id!r} agent={self.agent_type!r} status={self.status!r}>"


class LLMTokenUsage(BaseModel):
    """Track LLM token usage for analytics and cost reporting."""
    __tablename__ = "LLMTokenUsage"

    __create_sql__ = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='LLMTokenUsage' AND xtype='U')
    CREATE TABLE LLMTokenUsage (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        AgentType NVARCHAR(50) NOT NULL,
        AgentOperation NVARCHAR(50) NULL,
        ModelName NVARCHAR(50) NOT NULL,
        InputTokens INT NOT NULL,
        OutputTokens INT NOT NULL,
        InferenceRounds INT NULL DEFAULT 0,
        Description NVARCHAR(500) NULL,
        StartedAt DATETIME NOT NULL,
        CompletedAt DATETIME NULL,
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME NULL
    );

    IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_llm_agent_type' AND object_id = OBJECT_ID('LLMTokenUsage'))
    CREATE INDEX idx_llm_agent_type ON LLMTokenUsage(AgentType);

    IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_llm_created_at' AND object_id = OBJECT_ID('LLMTokenUsage'))
    CREATE INDEX idx_llm_created_at ON LLMTokenUsage(CreatedAt);
    """

    agent_type: Mapped[str] = mapped_column(
        "AgentType", String(50), nullable=False
    )
    agent_operation: Mapped[str | None] = mapped_column(
        "AgentOperation", String(50), nullable=True
    )
    model_name: Mapped[str] = mapped_column(
        "ModelName", String(50), nullable=False
    )
    input_tokens: Mapped[int] = mapped_column(
        "InputTokens", Integer, nullable=False
    )
    output_tokens: Mapped[int] = mapped_column(
        "OutputTokens", Integer, nullable=False
    )
    inference_rounds: Mapped[int | None] = mapped_column(
        "InferenceRounds", Integer, nullable=True, default=0
    )
    description: Mapped[str | None] = mapped_column(
        "Description", String(500), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        "StartedAt", DateTime, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        "CompletedAt", DateTime, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<LLMTokenUsage agent={self.agent_type!r} "
            f"model={self.model_name!r} tokens={self.input_tokens + self.output_tokens}>"
        )
