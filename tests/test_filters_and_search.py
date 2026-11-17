from app.services.filters import LocationRule, SearchFilters
from app.services.search import merge_results
from app.sniffers.hh.query import EmploymentForm, Experience, HHQuery, WorkFormat
from tests.conftest import make_vacancy


def test_filters_roundtrip_keeps_everything():
    f = SearchFilters(
        text="python",
        employment_forms={EmploymentForm.FULL},
        experiences={Experience.BETWEEN_1_AND_3},
        only_with_salary=True,
    )
    f.apply_remote_plus_home(53)
    f.set_exclude_words("Senior, lead")

    restored = SearchFilters.from_dict(f.to_dict())

    assert restored == f
    assert restored.locations[1] == LocationRule(area_id=53, work_formats={WorkFormat.ON_SITE, WorkFormat.HYBRID})


def test_old_saved_filter_without_new_fields_loads():
    f = SearchFilters.from_dict({"text": "go"})
    assert f.exclude_words == []
    assert len(f.locations) == 1


def test_exclude_words_parsing_and_matching():
    f = SearchFilters(text="python")
    f.set_exclude_words("Senior, lead; 1С\nlead, ")

    assert f.exclude_words == ["senior", "lead", "1с"]
    assert f.is_excluded("Senior Python Developer")
    assert f.is_excluded("Программист 1С")
    assert not f.is_excluded("Junior Python Developer")

    f.set_exclude_words("")
    assert f.exclude_words == []


def test_queries_sorted_by_date_for_subscriptions_and_multi_location():
    single = SearchFilters(text="python")
    assert "order_by" not in single.to_hh_queries()[0].get_url()
    assert "order_by=publication_time" in single.to_hh_queries(newest_first=True)[0].get_url()

    multi = SearchFilters(text="python")
    multi.apply_remote_plus_home(53)
    urls = [q.get_url() for q in multi.to_hh_queries()]
    assert len(urls) == 2
    assert all("order_by=publication_time" in u for u in urls)
    assert "work_format=REMOTE" in urls[0] and "area=113" in urls[0]
    assert "area=53" in urls[1]


def test_query_url_has_no_internal_fields():
    url = HHQuery(text="py", base_url="https://krasnodar.hh.ru/search/vacancy").get_url()
    assert url.startswith("https://krasnodar.hh.ru/search/vacancy?")
    assert "base_url" not in url


def test_merge_interleaves_locations_and_dedupes():
    remote = [make_vacancy("A", vid="1"), make_vacancy("B", vid="2"), make_vacancy("Same", "X", vid="3")]
    city = [make_vacancy("C", vid="4"), make_vacancy("Same", "X", vid="5")]  # та же вакансия в другом городе

    merged, matched = merge_results([remote, city])

    # ранги: A, C | B, Same(5) | Same(3) — дубль; остаётся тот, что встретился первым (id 5)
    assert [v.title for v in merged] == ["A", "C", "B", "Same"]
    assert sorted(matched["5"]) == [0, 1]
    assert "3" not in matched
