#!/usr/bin/env python3
"""
Скрипт для генерации детального отчета о покрытии кода тестами
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any


def run_command(cmd: List[str], description: str = "") -> tuple[bool, str, str]:
    """Запуск команды с логированием"""
    print(f"\n🚀 {description}")
    print(f"Команда: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Успешно")
    else:
        print("❌ Ошибка")
        print(f"STDERR: {result.stderr}")
    
    return result.returncode == 0, result.stdout, result.stderr


def analyze_coverage_data() -> Dict[str, Any]:
    """Анализирует данные покрытия кода"""
    coverage_file = Path("tests/reports/coverage.json")
    
    if not coverage_file.exists():
        print("⚠️ Файл coverage.json не найден. Запустите тесты с покрытием сначала.")
        return {}
    
    with open(coverage_file, 'r') as f:
        coverage_data = json.load(f)
    
    # Анализируем покрытие по файлам
    files_analysis = {}
    total_statements = 0
    total_missing = 0
    
    for file_path, file_data in coverage_data.get("files", {}).items():
        statements = file_data.get("summary", {}).get("num_statements", 0)
        missing = file_data.get("summary", {}).get("missing_lines", 0)
        covered = statements - missing
        coverage_percent = (covered / statements * 100) if statements > 0 else 0
        
        files_analysis[file_path] = {
            "statements": statements,
            "covered": covered,
            "missing": missing,
            "coverage_percent": coverage_percent,
            "missing_lines": file_data.get("missing_lines", [])
        }
        
        total_statements += statements
        total_missing += missing
    
    # Общая статистика
    total_covered = total_statements - total_missing
    overall_coverage = (total_covered / total_statements * 100) if total_statements > 0 else 0
    
    return {
        "overall": {
            "statements": total_statements,
            "covered": total_covered,
            "missing": total_missing,
            "coverage_percent": overall_coverage
        },
        "files": files_analysis,
        "timestamp": time.time()
    }


def generate_component_analysis() -> Dict[str, Any]:
    """Анализирует покрытие по компонентам системы"""
    
    components = {
        "TranscriptionAgent": ["pipeline/transcription_agent.py"],
        "DiarizationAgent": ["pipeline/diarization_agent.py"],
        "AudioLoaderAgent": ["pipeline/audio_agent.py"],
        "ExportAgent": ["pipeline/export_agent.py"],
        "MergeAgent": ["pipeline/merge_agent.py"],
        "VoiceprintAgent": ["pipeline/voiceprint_agent.py"],
        "WebhookAgent": ["pipeline/webhook_agent.py"],
        "QCAgent": ["pipeline/qc_agent.py"],
        "PyannoteMediaAgent": ["pipeline/pyannote_media_agent.py"],
        "Configuration": ["pipeline/config.py"],
        "Utils": ["pipeline/utils.py"]
    }
    
    coverage_data = analyze_coverage_data()
    component_analysis = {}
    
    for component_name, file_paths in components.items():
        component_stats = {
            "statements": 0,
            "covered": 0,
            "missing": 0,
            "coverage_percent": 0,
            "files": []
        }
        
        for file_path in file_paths:
            if file_path in coverage_data.get("files", {}):
                file_data = coverage_data["files"][file_path]
                component_stats["statements"] += file_data["statements"]
                component_stats["covered"] += file_data["covered"]
                component_stats["missing"] += file_data["missing"]
                component_stats["files"].append({
                    "path": file_path,
                    "coverage": file_data["coverage_percent"]
                })
        
        if component_stats["statements"] > 0:
            component_stats["coverage_percent"] = (
                component_stats["covered"] / component_stats["statements"] * 100
            )
        
        component_analysis[component_name] = component_stats
    
    return component_analysis


def generate_markdown_report(coverage_data: Dict[str, Any], component_data: Dict[str, Any]) -> str:
    """Генерирует отчет в формате Markdown"""
    
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    overall = coverage_data.get("overall", {})
    
    report = f"""# 📊 Отчет о покрытии кода тестами

**Дата генерации:** {timestamp}  
**Общее покрытие:** {overall.get('coverage_percent', 0):.1f}%

---

## 📈 Общая статистика

| Метрика | Значение |
|---------|----------|
| **Всего строк кода** | {overall.get('statements', 0)} |
| **Покрыто тестами** | {overall.get('covered', 0)} |
| **Не покрыто** | {overall.get('missing', 0)} |
| **Процент покрытия** | {overall.get('coverage_percent', 0):.1f}% |

---

## 🧩 Покрытие по компонентам

| Компонент | Покрытие | Строк | Покрыто | Не покрыто | Статус |
|-----------|----------|-------|---------|------------|--------|
"""
    
    # Сортируем компоненты по покрытию (по убыванию)
    sorted_components = sorted(
        component_data.items(), 
        key=lambda x: x[1].get('coverage_percent', 0), 
        reverse=True
    )
    
    for component_name, stats in sorted_components:
        coverage_pct = stats.get('coverage_percent', 0)
        status = "✅" if coverage_pct >= 80 else "⚠️" if coverage_pct >= 60 else "❌"
        
        report += f"| **{component_name}** | {coverage_pct:.1f}% | {stats.get('statements', 0)} | {stats.get('covered', 0)} | {stats.get('missing', 0)} | {status} |\n"
    
    report += """
---

## 📋 Детализация по файлам

### ✅ Хорошо покрытые файлы (>80%)

"""
    
    # Файлы с хорошим покрытием
    good_files = []
    medium_files = []
    poor_files = []
    
    for file_path, file_data in coverage_data.get("files", {}).items():
        coverage_pct = file_data.get("coverage_percent", 0)
        if coverage_pct >= 80:
            good_files.append((file_path, file_data))
        elif coverage_pct >= 60:
            medium_files.append((file_path, file_data))
        else:
            poor_files.append((file_path, file_data))
    
    for file_path, file_data in sorted(good_files, key=lambda x: x[1]['coverage_percent'], reverse=True):
        report += f"- **{file_path}**: {file_data['coverage_percent']:.1f}% ({file_data['covered']}/{file_data['statements']} строк)\n"
    
    if medium_files:
        report += "\n### ⚠️ Средне покрытые файлы (60-80%)\n\n"
        for file_path, file_data in sorted(medium_files, key=lambda x: x[1]['coverage_percent'], reverse=True):
            report += f"- **{file_path}**: {file_data['coverage_percent']:.1f}% ({file_data['covered']}/{file_data['statements']} строк)\n"
    
    if poor_files:
        report += "\n### ❌ Слабо покрытые файлы (<60%)\n\n"
        for file_path, file_data in sorted(poor_files, key=lambda x: x[1]['coverage_percent'], reverse=True):
            missing_lines = file_data.get('missing_lines', [])
            missing_str = f" - Непокрытые строки: {missing_lines[:10]}" if missing_lines else ""
            if len(missing_lines) > 10:
                missing_str += f" и еще {len(missing_lines) - 10}..."
            report += f"- **{file_path}**: {file_data['coverage_percent']:.1f}% ({file_data['covered']}/{file_data['statements']} строк){missing_str}\n"
    
    report += """
---

## 🎯 Рекомендации по улучшению

### Приоритетные задачи:
"""
    
    # Генерируем рекомендации
    if overall.get('coverage_percent', 0) < 80:
        report += "1. **Увеличить общее покрытие до 80%+**\n"
    
    if poor_files:
        report += f"2. **Добавить тесты для {len(poor_files)} слабо покрытых файлов**\n"
    
    if medium_files:
        report += f"3. **Улучшить покрытие для {len(medium_files)} файлов со средним покрытием**\n"
    
    report += """
### Следующие шаги:
- Добавить unit тесты для непокрытых функций
- Создать интеграционные тесты для сложных сценариев
- Добавить edge-case тесты для граничных условий
- Регулярно мониторить изменения покрытия

---

## 📊 Тренды качества

| Цель | Текущее значение | Статус |
|------|------------------|--------|
| Покрытие >80% | {overall.get('coverage_percent', 0):.1f}% | {'✅' if overall.get('coverage_percent', 0) >= 80 else '❌'} |
| Все компоненты >70% | {len([c for c in component_data.values() if c.get('coverage_percent', 0) >= 70])}/{len(component_data)} | {'✅' if all(c.get('coverage_percent', 0) >= 70 for c in component_data.values()) else '❌'} |
| Нет файлов <50% | {len([f for f in coverage_data.get('files', {}).values() if f.get('coverage_percent', 0) < 50])} файлов | {'✅' if not any(f.get('coverage_percent', 0) < 50 for f in coverage_data.get('files', {}).values()) else '❌'} |

---

*Отчет сгенерирован автоматически: {timestamp}*
"""
    
    return report


def main():
    print("📊 Генерация отчета о покрытии кода тестами")
    
    # Создаем директорию для отчетов
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Запускаем тесты с покрытием
    success, stdout, stderr = run_command([
        "python3", "-m", "pytest", "tests/", 
        "--cov=pipeline", 
        "--cov-report=json:tests/reports/coverage.json",
        "--cov-report=html:tests/reports/coverage",
        "--cov-report=term-missing",
        "-q"
    ], "Запуск тестов с анализом покрытия")
    
    if not success:
        print("❌ Не удалось запустить тесты с покрытием")
        return 1
    
    # Анализируем данные покрытия
    print("\n📊 Анализ данных покрытия...")
    coverage_data = analyze_coverage_data()
    
    if not coverage_data:
        print("❌ Не удалось получить данные покрытия")
        return 1
    
    # Анализируем покрытие по компонентам
    print("🧩 Анализ покрытия по компонентам...")
    component_data = generate_component_analysis()
    
    # Генерируем отчет
    print("📝 Генерация отчета...")
    markdown_report = generate_markdown_report(coverage_data, component_data)
    
    # Сохраняем отчет
    report_path = reports_dir / "coverage_analysis.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    # Сохраняем JSON данные для дальнейшего анализа
    analysis_data = {
        "coverage": coverage_data,
        "components": component_data,
        "timestamp": time.time()
    }
    
    json_path = reports_dir / "coverage_analysis.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    
    # Выводим краткую сводку
    overall = coverage_data.get("overall", {})
    print(f"\n📊 Краткая сводка:")
    print(f"   Общее покрытие: {overall.get('coverage_percent', 0):.1f}%")
    print(f"   Покрыто строк: {overall.get('covered', 0)}/{overall.get('statements', 0)}")
    print(f"   Компонентов с покрытием >80%: {len([c for c in component_data.values() if c.get('coverage_percent', 0) >= 80])}/{len(component_data)}")
    
    print(f"\n📄 Отчеты сохранены:")
    print(f"   Markdown: {report_path}")
    print(f"   JSON: {json_path}")
    print(f"   HTML: tests/reports/coverage/index.html")
    
    print("\n🎉 Анализ покрытия завершен!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
