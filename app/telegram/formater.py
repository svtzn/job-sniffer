def format_vacancies(vacancies: list[dict], query_text: str, page: int = 0, total: int = 0) -> str:
    pages = max(1, (total + 2) // 3) if total > 0 else 1
    header = f"🔍 Найдено: {total} вакансий" if total else "🔍 По запросу «{query_text}» вакансий не найдено"
    if pages > 1:
        header += f" (стр. {page + 1}/{pages})"

    if not vacancies:
        return header

    lines = [header, ""]
    for i, v in enumerate(vacancies, 1):
        salary = v.get("salary", "") or "ЗП не указана"
        exp = v.get("experience", "") or "Опыт не указан"
        loc = v.get("location", "") or "Местоположение не указано"
        emp = v.get("employer", "") or "Наниматель не указан"

        lines.append(f"{i}. {v.get('title', 'Без названия')}")
        lines.append(f"   💰 {salary}")
        lines.append(f"   🏢 {emp}")
        lines.append(f"   📍 {loc}")
        lines.append(f"   📋 {exp}")
        lines.append(f"   🔗 {v.get('url', '')}")
        lines.append("")

    return "\n".join(lines)
