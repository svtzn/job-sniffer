import asyncio
from app.sniffers.hh.sniffer import HHSniffer
from app.sniffers.hh.query import HHQuery
from app.config import get_settings


async def main():
    config = get_settings()
    sniffer = HHSniffer(config)

    try:
        await sniffer.start()
    except PermissionError as e:
        print(f"[ERROR] Не удалось запустить браузер: {e}")
        print("Проверь: антивирус / групповые политики блокируют subprocess.")
        print("Запусти из своего терминала — скорее всего сработает.")
        return

    try:
        query = HHQuery(
            text='fastapi',
            work_format='REMOTE',
            label='with_salary'
        )
        vacancies = await sniffer.fetch_vacancies(query)
        print(f"[DEBUG] Found {len(vacancies)} vacancies")

        for v in vacancies:
            print(v)
    finally:
        await sniffer.stop()


if __name__ == "__main__":
    asyncio.run(main())
