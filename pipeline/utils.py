"""
Вспомогательные функции для speech pipeline.
"""

import json
from pathlib import Path
from typing import Dict, Any


def load_json(path: Path) -> Dict[str, Any]:
    """
    Загружает JSON-файл и возвращает его содержимое как словарь.
    
    Args:
        path: Путь к JSON-файлу
        
    Returns:
        Словарь с содержимым JSON-файла
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict[str, Any], path: Path) -> None:
    """
    Сохраняет словарь в JSON-файл.
    
    Args:
        data: Словарь для сохранения
        path: Путь к JSON-файлу
    """
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
