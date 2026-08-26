from bs4 import BeautifulSoup


class HHParser:

    def parse_vacancies(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        card_selectors = [
            '[data-qa="vacancy-serp__vacancy"]',
            '[data-marker="vacancy"]',
            '.serp-item',
            '[data-qa="vacancy-preview"]',
        ]
        cards = []
        for sel in card_selectors:
            cards = soup.select(sel)
            if cards:
                break

        if not cards:
            print("[DEBUG] No vacancy cards found with any selector")
            return []

        vacancies = []
        seen_urls = set()

        for card in cards:
            # title
            title_el = card.select_one('[data-qa="serp-item__title-text"]')
            if not title_el:
                title_el = card.select_one('[data-marker="vacancy-title"]')
            if not title_el:
                title_el = card.select_one('.serp-item__title')
            vacancy_title = title_el.get_text(strip=True) if title_el else ""

            # url
            href_el = card.select_one('[data-qa="serp-item__title"][href]')
            if not href_el:
                href_el = card.select_one('[data-marker="vacancy-title"]')
            if not href_el:
                href_el = card.select_one('.serp-item__title a')
            vacancy_url = (href_el.get("href") or "") if href_el else ""
            if not vacancy_url or vacancy_url in seen_urls:
                continue
            if vacancy_url.startswith("//"):
                vacancy_url = "https:" + vacancy_url
            elif vacancy_url.startswith("/"):
                vacancy_url = "https://hh.ru" + vacancy_url
            seen_urls.add(vacancy_url)

            # id
            start_id_str = "vacancy/"
            end_id_str = "?"
            start_id_index = vacancy_url.find(start_id_str) + len(start_id_str)
            end_id_index = vacancy_url.find(end_id_str) 
            vacancy_id = vacancy_url[start_id_index:end_id_index]

            # salary
            data_tags = card.select("data[value]")
            salary_parts = []
            for tag in data_tags:
                val = tag.get("value", "")
                if val and val.isdigit():
                    salary_parts.append(val)
                elif tag.get_text(strip=True) in ("$", "₽", "€", "£", "₴", "₸", "₼"):
                    salary_parts.append(tag.get_text(strip=True))
            if salary_parts:
                vacancy_salary = " ".join(salary_parts)
            else:
                vacancy_salary = "Зарплата не указана"

            # experience
            exp_el = card.select_one('[data-qa^="vacancy-serp__vacancy-work-experience"]')
            if not exp_el:
                exp_el = card.select_one('[data-marker="vacancy-sector-experience"]')
            if not exp_el:
                exp_el = card.select_one('.vacancy-item__experience')
            vacancy_experience = exp_el.get_text(strip=True) if exp_el else "Опыт не указан"

            # location
            loc_el = card.select_one('[data-qa="vacancy-serp__vacancy-address"]')
            if not loc_el:
                loc_el = card.select_one('[data-marker="vacancy-sector-location"]')
            if not loc_el:
                loc_el = card.select_one('.vacancy-item__address')
            vacancy_location = loc_el.get_text(strip=True) if loc_el else "Местоположение не указано"

            # employer
            employer_el = card.select_one('[data-qa="vacancy-serp__vacancy-employer-text"]')
            if not employer_el:
                employer_el = card.select_one('[data-marker="vacancy-sector-employer"]')
            if not employer_el:
                employer_el = card.select_one('.vacancy-item__employer')
            vacancy_employer = employer_el.get_text(strip=True) if employer_el else "Наниматель не указан"

            vacancy = {
                "id": vacancy_id,
                "title": vacancy_title,
                "url": vacancy_url,
                "salary": vacancy_salary,
                "experience": vacancy_experience,
                "location": vacancy_location,
                "employer": vacancy_employer,
            }
            vacancies.append(vacancy)

        return vacancies
