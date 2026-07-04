# ui/workflow/node_registry.py
"""Registry of available workflow node types and their metadata."""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Node type definitions
# ---------------------------------------------------------------------------

NODE_TYPES: dict[str, dict[str, Any]] = {
    "text_prompt": {
        "title": "Text Prompt",
        "icon": "\uE8C8",
        "category": "Input",
        "color": "#8b5cf6",
        "runnable": False,
        "inputs": [],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "prompt", "type": "textarea", "label": "Prompt", "default": ""},
        ],
    },
    "upload_image": {
        "title": "Upload Ảnh",
        "icon": "\uEB9F",
        "category": "Input",
        "color": "#06b6d4",
        "runnable": False,
        "inputs": [],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "images", "type": "image_upload", "label": "Chọn ảnh", "default": []},
        ],
    },
    "upload_video": {
        "title": "Upload Video",
        "icon": "\uE714",
        "category": "Input",
        "color": "#14b8a6",
        "runnable": False,
        "inputs": [],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "videos", "type": "video_upload", "label": "Chọn video", "default": []},
        ],
    },
    "generate_image": {
        "title": "Tạo Ảnh",
        "icon": "\uEB9F",
        "category": "AI",
        "color": "#f59e0b",
        "inputs": [
            {"name": "input", "type": "any"},
        ],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "model", "type": "combo", "label": "Mô hình", "options": ["🍌 Nano Banana 2", "🍌 Nano Banana Pro", "✨ Imagen 4"], "default": "🍌 Nano Banana 2"},
            {"name": "ratio", "type": "combo", "label": "Tỷ lệ", "options": ["16:9", "4:3", "1:1", "3:4", "9:16"], "default": "16:9"},
            {"name": "count", "type": "combo", "label": "Số ảnh", "options": ["1", "2", "3", "4"], "default": "1"},
        ],
    },
    "generate_video": {
        "title": "Tạo Video",
        "icon": "\uE714",
        "category": "AI",
        "color": "#6366f1",
        "inputs": [
            {"name": "input", "type": "any"},
        ],
        "outputs": [{"name": "output", "type": "any"}],
        "config_tabs": [
            {
                "name": "Khung hình",
                "fields": [
                    {"name": "frames", "type": "frame_pair", "label": "", "default": {"start": [], "end": []}},
                ]
            },
            {
                "name": "Thành phần",
                "fields": [
                    {"name": "reference_image", "type": "image_upload", "label": "Ảnh tham chiếu"},
                ],
            }
        ],
        "global_fields": [
            {
                "name": "ratio",
                "type": "combo",
                "label": "Tỷ lệ",
                "default": "16:9",
                "options": ["9:16", "16:9"],
            },
            {
                "name": "count",
                "type": "combo",
                "label": "Số video",
                "options": ["1", "2", "3", "4"],
                "default": "1",
            },
            {
                "name": "model",
                "type": "combo",
                "label": "Mô hình",
                "default": "Veo 3.1 - Lite [Lower Priority]",
                "options": [
                    "Omni Flash",
                    "Veo 3.1 - Lite",
                    "Veo 3.1 - Fast",
                    "Veo 3.1 - Quality",
                    "Veo 3.1 - Lite [Lower Priority]",
                ],
            },
            {
                "name": "duration",
                "type": "combo",
                "label": "Thời lượng",
                "default": "8s",
                "options": ["4s", "6s", "8s"],
            },
        ],

    },
    "merge_video": {
        "title": "Nối Video",
        "icon": "\uE71B",
        "category": "Process",
        "color": "#f59e0b",
        "inputs": [{"name": "input", "type": "any"}],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "videos", "type": "video_list", "label": "Danh sách video", "default": []},
        ],
    },
    "download": {
        "title": "Tải xuống",
        "icon": "\uE896",
        "category": "Output",
        "color": "#10b981",
        "inputs": [
            {"name": "input", "type": "any"},
        ],
        "outputs": [],
        "config_fields": [
            {
                "name": "quality",
                "type": "combo",
                "label": "Chất lượng",
                "default": "Gốc",
                "options": ["Gốc", "1080p", "2K", "4K"],
            },
            {"name": "output_dir", "type": "folder", "label": "Thư mục lưu", "default": ""},
        ],
    },
    "history": {
        "title": "Lịch sử tạo",
        "icon": "\uE81C",
        "category": "Output",
        "color": "#6366f1",
        "inputs": [],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "media_type", "type": "combo", "label": "Loại", "options": ["Video", "Ảnh"], "default": "Video"},
            {"name": "items", "type": "history_picker", "label": "Chọn nội dung", "default": []},
        ],
    },
    "delay": {
        "title": "Delay",
        "icon": "\uE916",
        "category": "Process",
        "color": "#6b7280",
        "inputs": [{"name": "input", "type": "any"}],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "seconds", "type": "number", "label": "Giây", "default": 5},
        ],
    },
    "preview": {
        "title": "Xem trước",
        "icon": "\uE890",
        "category": "Output",
        "color": "#ec4899",
        "inputs": [
            {"name": "input", "type": "any"},
        ],
        "outputs": [{"name": "output", "type": "any"}],
        "config_fields": [
            {"name": "preview_data", "type": "media_preview", "label": "Preview", "default": []}
        ],
    },
}


NODE_CATEGORIES: dict[str, list[str]] = {
    "Input": ["text_prompt", "upload_image", "upload_video"],
    "AI": ["generate_image", "generate_video"],
    "Process": ["merge_video"],
    "Output": ["download", "preview", "history"],
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_node_type(type_name: str) -> dict[str, Any]:
    """Return the node-type definition dict, or an empty dict if unknown."""
    return NODE_TYPES.get(type_name, {})


def get_all_categories() -> dict[str, list[str]]:
    """Return the ordered mapping  *category_name → [node_type_key, …]*."""
    return dict(NODE_CATEGORIES)


def can_connect(source_type: str, target_type: str) -> bool:
    """Check whether *source_type* is assignment-compatible with *target_type*.

    Rules:
    * ``"any"`` on either side matches everything.
    * Otherwise the types must match exactly.
    """
    if source_type == "any" or target_type == "any":
        return True
    return source_type == target_type
