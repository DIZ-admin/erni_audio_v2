"""
VoiceprintManager для управления базой голосовых отпечатков
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import uuid
from datetime import datetime
import threading


class VoiceprintManager:
    """
    Менеджер для управления базой голосовых отпечатков.
    
    Обеспечивает сохранение, загрузку, поиск и управление голосовыми отпечатками
    в локальной JSON базе данных.
    """
    
    def __init__(self, database_path: Path = Path("voiceprints/voiceprints.json")):
        """
        Инициализация VoiceprintManager.
        
        Args:
            database_path: Путь к JSON файлу с базой голосовых отпечатков
        """
        self.database_path = database_path
        self.logger = logging.getLogger(__name__)
        
        # Создаем директорию если не существует
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Блокировка для thread-safe операций
        self._lock = threading.Lock()

        # Загружаем существующую базу или создаем новую
        self.voiceprints = self._load_database()
        
        self.logger.info(f"✅ VoiceprintManager инициализирован: {len(self.voiceprints)} voiceprints")
    
    def add_voiceprint(self,
                      label: str,
                      voiceprint_data: str,
                      source_file: str = "",
                      metadata: Optional[Dict] = None) -> str:
        """
        Добавляет новый голосовой отпечаток в базу.

        Args:
            label: Человекочитаемое имя (например, "John Doe")
            voiceprint_data: Base64 данные голосового отпечатка
            source_file: Путь к исходному аудиофайлу
            metadata: Дополнительные метаданные

        Returns:
            UUID созданного voiceprint
        """
        # Валидация входных данных
        if not label or not label.strip():
            raise ValueError("Label не может быть пустым")

        if not voiceprint_data or not voiceprint_data.strip():
            raise ValueError("Voiceprint data не может быть пустым")

        voiceprint_id = str(uuid.uuid4())
        
        voiceprint_entry = {
            "id": voiceprint_id,
            "label": label,
            "voiceprint": voiceprint_data,
            "source_file": source_file,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.voiceprints[voiceprint_id] = voiceprint_entry
        self._save_database()
        
        self.logger.info(f"✅ Добавлен voiceprint '{label}' (ID: {voiceprint_id[:8]}...)")
        return voiceprint_id
    
    def get_voiceprint(self, voiceprint_id: str) -> Optional[Dict]:
        """
        Получает голосовой отпечаток по ID.
        
        Args:
            voiceprint_id: UUID голосового отпечатка
            
        Returns:
            Словарь с данными voiceprint или None если не найден
        """
        return self.voiceprints.get(voiceprint_id)
    
    def get_voiceprint_by_label(self, label: str) -> Optional[Dict]:
        """
        Получает голосовой отпечаток по человекочитаемому имени.
        
        Args:
            label: Человекочитаемое имя
            
        Returns:
            Словарь с данными voiceprint или None если не найден
        """
        for voiceprint in self.voiceprints.values():
            if voiceprint["label"].lower() == label.lower():
                return voiceprint
        return None
    
    def list_voiceprints(self) -> List[Dict]:
        """
        Возвращает список всех голосовых отпечатков.
        
        Returns:
            Список словарей с данными voiceprints
        """
        return list(self.voiceprints.values())
    
    def search_voiceprints(self, query: str) -> List[Dict]:
        """
        Поиск голосовых отпечатков по запросу.
        
        Args:
            query: Поисковый запрос (ищет в label и metadata)
            
        Returns:
            Список найденных voiceprints
        """
        query_lower = query.lower()
        results = []
        
        for voiceprint in self.voiceprints.values():
            # Поиск в label
            if query_lower in voiceprint["label"].lower():
                results.append(voiceprint)
                continue
            
            # Поиск в metadata
            metadata_str = json.dumps(voiceprint.get("metadata", {})).lower()
            if query_lower in metadata_str:
                results.append(voiceprint)
        
        return results
    
    def delete_voiceprint(self, voiceprint_id: str) -> bool:
        """
        Удаляет голосовой отпечаток из базы.
        
        Args:
            voiceprint_id: UUID голосового отпечатка
            
        Returns:
            True если удален, False если не найден
        """
        if voiceprint_id in self.voiceprints:
            label = self.voiceprints[voiceprint_id]["label"]
            del self.voiceprints[voiceprint_id]
            self._save_database()
            self.logger.info(f"🗑️ Удален voiceprint '{label}' (ID: {voiceprint_id[:8]}...)")
            return True
        return False
    
    def update_voiceprint(self, voiceprint_id: str, **updates) -> bool:
        """
        Обновляет данные голосового отпечатка.
        
        Args:
            voiceprint_id: UUID голосового отпечатка
            **updates: Поля для обновления
            
        Returns:
            True если обновлен, False если не найден
        """
        if voiceprint_id not in self.voiceprints:
            return False
        
        voiceprint = self.voiceprints[voiceprint_id]
        
        # Обновляем разрешенные поля
        allowed_fields = ["label", "metadata", "source_file"]
        for field, value in updates.items():
            if field in allowed_fields:
                voiceprint[field] = value
        
        voiceprint["updated_at"] = datetime.now().isoformat()
        self._save_database()
        
        self.logger.info(f"📝 Обновлен voiceprint '{voiceprint['label']}' (ID: {voiceprint_id[:8]}...)")
        return True
    
    def get_voiceprints_for_identification(self, labels: List[str]) -> List[Dict]:
        """
        Получает voiceprints в формате для Identification API.
        
        Args:
            labels: Список человекочитаемых имен
            
        Returns:
            Список voiceprints в формате [{"label": str, "voiceprint": str}, ...]
        """
        result = []
        
        for label in labels:
            voiceprint = self.get_voiceprint_by_label(label)
            if voiceprint:
                result.append({
                    "label": voiceprint["label"],
                    "voiceprint": voiceprint["voiceprint"]
                })
            else:
                self.logger.warning(f"⚠️ Voiceprint не найден для '{label}'")
        
        return result
    
    def export_voiceprints(self, output_path: Path, labels: Optional[List[str]] = None) -> None:
        """
        Экспортирует voiceprints в JSON файл.
        
        Args:
            output_path: Путь для сохранения
            labels: Список имен для экспорта (None для всех)
        """
        if labels:
            voiceprints_to_export = {}
            for label in labels:
                voiceprint = self.get_voiceprint_by_label(label)
                if voiceprint:
                    voiceprints_to_export[voiceprint["id"]] = voiceprint
        else:
            voiceprints_to_export = self.voiceprints
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(voiceprints_to_export, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"📤 Экспортировано {len(voiceprints_to_export)} voiceprints в {output_path}")
    
    def import_voiceprints(self, input_path: Path, overwrite: bool = False) -> int:
        """
        Импортирует voiceprints из JSON файла.
        
        Args:
            input_path: Путь к JSON файлу
            overwrite: Перезаписывать ли существующие voiceprints
            
        Returns:
            Количество импортированных voiceprints
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            imported_voiceprints = json.load(f)
        
        imported_count = 0
        
        for voiceprint_id, voiceprint_data in imported_voiceprints.items():
            if voiceprint_id in self.voiceprints and not overwrite:
                self.logger.warning(f"⚠️ Voiceprint {voiceprint_id} уже существует, пропускаем")
                continue
            
            self.voiceprints[voiceprint_id] = voiceprint_data
            imported_count += 1
        
        self._save_database()
        self.logger.info(f"📥 Импортировано {imported_count} voiceprints из {input_path}")
        return imported_count
    
    def get_statistics(self) -> Dict:
        """
        Возвращает статистику по базе voiceprints.

        Returns:
            Словарь со статистикой
        """
        created_dates = [vp.get("created_at", "") for vp in self.voiceprints.values()]
        valid_dates = [date for date in created_dates if date]

        stats = {
            "total": len(self.voiceprints),
            "labels": [vp["label"] for vp in self.voiceprints.values()] if self.voiceprints else [],
            "oldest": min(valid_dates) if valid_dates else None,
            "newest": max(valid_dates) if valid_dates else None,
            "database_path": str(self.database_path),
            "database_size_kb": round(self.database_path.stat().st_size / 1024, 2) if self.database_path.exists() else 0
        }

        return stats
    
    def _load_database(self) -> Dict:
        """Загружает базу voiceprints из JSON файла."""
        if self.database_path.exists():
            try:
                with open(self.database_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.logger.info(f"📥 Загружена база voiceprints: {len(data)} записей")
                return data
            except Exception as e:
                self.logger.error(f"❌ Ошибка загрузки базы voiceprints: {e}")
                self.logger.info("🆕 Создаю новую базу voiceprints")
        
        return {}
    
    def _save_database(self) -> None:
        """Сохраняет базу voiceprints в JSON файл."""
        try:
            with self._lock:
                # Создаем копию для безопасной сериализации
                voiceprints_copy = dict(self.voiceprints)
                with open(self.database_path, 'w', encoding='utf-8') as f:
                    json.dump(voiceprints_copy, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"❌ Ошибка сохранения базы voiceprints: {e}")
            raise
