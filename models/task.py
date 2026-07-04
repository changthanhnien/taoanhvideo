"""VidGen AI — Task and TaskItem models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.constants import ItemStatus, TaskMode, TaskStatus


@dataclass
class TaskItem:
    """Single prompt result within a task."""

    id: int = 0
    task_id: int = 0
    prompt: str = ""
    reference_image: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    status: str = ItemStatus.PENDING
    output_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    generation_id: Optional[str] = None
    error_message: Optional[str] = None
    credit_cost: int = 0
    completed_at: Optional[datetime] = None
    flow_project_id: Optional[str] = None
    gen_account_id: Optional[int] = None

    @property
    def is_done(self) -> bool:
        return self.status == ItemStatus.COMPLETED

    @property
    def is_error(self) -> bool:
        return self.status == ItemStatus.ERROR

    @property
    def is_pending(self) -> bool:
        return self.status == ItemStatus.PENDING

    @classmethod
    def from_row(cls, row) -> TaskItem:
        def _parse_dt(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        if hasattr(row, "keys") or isinstance(row, dict):
            return cls(
                id=row["id"],
                task_id=row["task_id"],
                prompt=row["prompt"],
                reference_image=row["reference_image"],
                start_frame=row["start_frame"],
                end_frame=row["end_frame"],
                status=row["status"] or ItemStatus.PENDING,
                output_path=row["output_path"],
                thumbnail_path=row["thumbnail_path"],
                generation_id=row["generation_id"],
                error_message=row["error_message"],
                credit_cost=row["credit_cost"] or 0,
                completed_at=_parse_dt(row["completed_at"]),
                flow_project_id=row["flow_project_id"] if "flow_project_id" in row.keys() else None,
                gen_account_id=row["gen_account_id"] if "gen_account_id" in row.keys() else None,
            )

        return cls(
            id=row[0],
            task_id=row[1],
            prompt=row[2],
            reference_image=row[3],
            start_frame=row[4],
            end_frame=row[5],
            status=row[6] or ItemStatus.PENDING,
            output_path=row[7],
            thumbnail_path=row[8],
            generation_id=row[9],
            error_message=row[10],
            credit_cost=row[11] or 0,
            completed_at=_parse_dt(row[12]),
            flow_project_id=row[13] if len(row) > 13 else None,
            gen_account_id=row[14] if len(row) > 14 else None,
        )


@dataclass
class VideoTask:
    """A batch task containing multiple prompts."""

    id: int = 0
    project_id: int = 0
    account_id: Optional[int] = None
    name: str = ""
    mode: str = TaskMode.VIDEO
    quality: str = "Veo 3.1 - Fast"
    image_model: str = "Nano Banana 2"
    aspect_ratio: str = "16:9"
    concurrent: int = 1
    parallel_per_account: int = 1
    character_images: list[str] = field(default_factory=list)
    input_folder: Optional[str] = None
    output_folder: str = ""
    delay: int = 0
    status: str = TaskStatus.PENDING
    total_count: int = 0
    done_count: int = 0
    error_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    items: list[TaskItem] = field(default_factory=list)
    config: Optional[str] = None  # JSON string with creation_mode, duration, uploaded_images etc.

    @property
    def progress(self) -> float:
        if self.total_count == 0:
            return 0
        return (self.done_count + self.error_count) / self.total_count

    @property
    def progress_text(self) -> str:
        return f"{self.done_count}/{self.total_count}"

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_image_mode(self) -> bool:
        return self.mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE)

    @property
    def is_video_task(self) -> bool:
        return self.mode in (TaskMode.CHAR_VIDEO, TaskMode.VIDEO, TaskMode.FRAME_VIDEO)

    @property
    def has_character_refs(self) -> bool:
        return self.mode in (TaskMode.CHAR_IMAGE, TaskMode.CHAR_VIDEO)

    def character_images_json(self) -> str:
        return json.dumps(self.character_images)

    @classmethod
    def from_row(cls, row) -> VideoTask:
        char_images = []
        def _parse_dt(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        if hasattr(row, "keys") or isinstance(row, dict):
            raw_char = row["character_images"]
            if raw_char:
                try:
                    char_images = json.loads(raw_char)
                except json.JSONDecodeError:
                    pass
            return cls(
                id=row["id"],
                project_id=row["project_id"],
                account_id=row["account_id"],
                name=row["name"],
                mode=row["mode"],
                quality=row["quality"],
                aspect_ratio=row["aspect_ratio"],
                concurrent=row["concurrent"] or 1,
                character_images=char_images,
                input_folder=row["input_folder"],
                output_folder=row["output_folder"] or "",
                status=row["status"] or TaskStatus.PENDING,
                total_count=row["total_count"] or 0,
                done_count=row["done_count"] or 0,
                error_count=row["error_count"] or 0,
                created_at=_parse_dt(row["created_at"]) or datetime.now(),
                image_model=row["image_model"] if "image_model" in row.keys() and row["image_model"] else "Nano Banana 2",
                delay=row["delay"] if "delay" in row.keys() and row["delay"] is not None else 0,
                config=row["config"] if "config" in row.keys() else None,
            )

        if row[8]:
            try:
                char_images = json.loads(row[8])
            except json.JSONDecodeError:
                pass
        return cls(
            id=row[0],
            project_id=row[1],
            account_id=row[2],
            name=row[3],
            mode=row[4],
            quality=row[5],
            aspect_ratio=row[6],
            concurrent=row[7] or 1,
            character_images=char_images,
            input_folder=row[9],
            output_folder=row[10] or "",
            status=row[11] or TaskStatus.PENDING,
            total_count=row[12] or 0,
            done_count=row[13] or 0,
            error_count=row[14] or 0,
            created_at=_parse_dt(row[15]) or datetime.now(),
            image_model=row[16] if len(row) > 16 and row[16] else "Nano Banana 2",
            delay=row[17] if len(row) > 17 and row[17] is not None else 0,
            config=row[18] if len(row) > 18 else None,
        )


@dataclass
class Project:
    """Project / folder grouping tasks by date."""

    id: int = 0
    name: str = ""
    folder_path: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_row(cls, row) -> Project:
        def _parse_dt(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        if hasattr(row, "keys") or isinstance(row, dict):
            return cls(
                id=row["id"],
                name=row["name"],
                folder_path=row["folder_path"] or "",
                created_at=_parse_dt(row["created_at"]) or datetime.now(),
            )
        return cls(
            id=row[0],
            name=row[1],
            folder_path=row[2] or "",
            created_at=_parse_dt(row[3]) or datetime.now(),
        )
