"""Тесты src/recommend.py — радио YouTube Music + дедуп по библиотеке."""
from __future__ import annotations

import random

import pytest

from src import recommend as rec


def tr(artist, title):
    return {"artist": artist, "title": title}


def cand(title, artist, video_id="vid-x", album="Alb", cover_url="cover.jpg"):
    """Кандидат в формате ytm_track_to_dict."""
    return {"video_id": video_id, "title": title, "artist": artist,
            "album": album, "cover_url": cover_url}


class TestPickSeeds:
    def test_spreads_across_artists(self):
        records = [tr("A", "1"), tr("A", "2"), tr("B", "1"), tr("C", "1")]
        seeds = rec.pick_seeds(records, 3)
        assert [s["artist"] for s in seeds] == ["A", "B", "C"]

    def test_round_robin_after_first_pass(self):
        records = [tr("A", "1"), tr("A", "2"), tr("A", "3"), tr("B", "1")]
        seeds = rec.pick_seeds(records, 10)
        assert [s["artist"] for s in seeds] == ["A", "B", "A", "A"]

    def test_limit(self):
        records = [tr(a, "1") for a in "ABCDEF"]
        assert len(rec.pick_seeds(records, 2)) == 2

    def test_empty(self):
        assert rec.pick_seeds([], 5) == []


class TestGenerate:
    def _radio(self, tracks):
        calls = {"n": 0}
        limits = []

        def fn(seed, limit):
            calls["n"] += 1
            limits.append(limit)
            return tracks

        return fn, calls, limits

    def test_basic_generation(self):
        records = [tr("SeedArtist", "Song"), tr("B", "X")]
        radio, calls, limits = self._radio([cand("Candidate", "OtherArtist")])
        res = rec.generate(records, radio_fn=radio, seed_limit=5, similar_limit=7)
        assert res["library_count"] == 2
        assert res["seeds"] == 2
        assert res["items"][0]["artist"] == "OtherArtist"
        assert res["items"][0]["title"] == "Candidate"
        assert res["items"][0]["album"] == "Alb"
        assert res["items"][0]["cover_url"] == "cover.jpg"
        assert res["items"][0]["url"] == "https://www.youtube.com/watch?v=vid-x"
        assert calls["n"] == 2
        assert limits == [7, 7]
        assert all("score" not in i for i in res["items"]), "низ без ранжирования"

    def test_order_preserved_from_radio(self):
        radio, _, _ = self._radio([
            cand("First", "A", "v1"),
            cand("Second", "B", "v2"),
            cand("Third", "C", "v3"),
        ])
        res = rec.generate([tr("Seed", "Song")], radio_fn=radio)
        assert [i["title"] for i in res["items"]] == ["First", "Second", "Third"]

    def test_interleaves_seeds_round_robin(self):
        """Кандидаты чередуются по сидам — нет блока «весь радио сида подряд»."""
        tracks = {
            ("A", "SongA"): [cand("A1", "X", "va1"), cand("A2", "X", "va2")],
            ("B", "SongB"): [cand("B1", "Y", "vb1"), cand("B2", "Y", "vb2")],
        }

        def radio(seed, limit):
            return tracks[(seed["artist"], seed["title"])]

        res = rec.generate([tr("A", "SongA"), tr("B", "SongB")],
                           radio_fn=radio, rng=random.Random(7))
        items = res["items"]
        assert res["total"] == 4
        assert sorted(i["title"] for i in items) == ["A1", "A2", "B1", "B2"]
        # Первые два кандидата — от разных сидов (round-robin).
        assert items[0]["seed"] != items[1]["seed"]
        # Внутри каждого сида порядок радио сохранён.
        by_seed = {}
        for i in items:
            by_seed.setdefault(i["seed"], []).append(i["title"])
        assert by_seed["A — SongA"] == ["A1", "A2"]
        assert by_seed["B — SongB"] == ["B1", "B2"]

    def test_same_rng_same_result(self):
        """Фиксированный rng — воспроизводимый порядок."""
        records = [tr("A", "SongA"), tr("B", "SongB"), tr("C", "SongC")]

        def radio(seed, limit):
            return [cand("Cand", f"Other-{seed['artist']}", f"v-{seed['artist']}")]

        r1 = rec.generate(records, radio_fn=radio, rng=random.Random(42))
        r2 = rec.generate(records, radio_fn=radio, rng=random.Random(42))
        assert [i["video_id"] for i in r1["items"]] == [i["video_id"] for i in r2["items"]]
        assert [i["seed"] for i in r1["items"]] == [i["seed"] for i in r2["items"]]

    def test_excludes_owned(self):
        radio, _, _ = self._radio([cand("Song", "SeedArtist"),
                                   cand("Track", "Owned"),
                                   cand("New", "Other")])
        res = rec.generate([tr("Seed", "Song"), tr("Owned", "Track")],
                           radio_fn=radio)
        assert [i["title"] for i in res["items"]] == ["New"]

    def test_excludes_owned_with_feat(self):
        """«Barry Bonds (feat. Lil Wayne)» ~ локальный «Barry Bonds»."""
        radio, _, _ = self._radio([
            cand("Barry Bonds (feat. Lil Wayne)", "Kanye West", "v1"),
            cand("Graduation Day", "Kanye West", "v2"),
        ])
        res = rec.generate([tr("Kanye West", "Barry Bonds")], radio_fn=radio)
        assert [i["title"] for i in res["items"]] == ["Graduation Day"]

    def test_excludes_owned_ignore_case_and_punct(self):
        radio, _, _ = self._radio([
            cand("The End!", "The Doors", "v1"),
        ])
        res = rec.generate([tr("The Doors", "the  end")], radio_fn=radio)
        assert res["items"] == []

    def test_dedupes_candidates_with_feat(self):
        """Повторы между кандидатами тоже сравниваются без фичей."""
        radio, _, _ = self._radio([
            cand("Good Life", "Kanye West", "v1"),
            cand("Good Life (feat. T-Pain)", "Kanye West", "v2"),
        ])
        res = rec.generate([tr("Seed", "Song")], radio_fn=radio)
        assert len(res["items"]) == 1

    def test_dedupes_candidates(self):
        radio, _, _ = self._radio([cand("C", "Other"), cand("C", "Other")])
        res = rec.generate([tr("Seed", "Song")], radio_fn=radio)
        assert len(res["items"]) == 1

    def test_skips_blank_title(self):
        radio, _, _ = self._radio([cand(" ", "Other"), cand("Ok", "Other")])
        res = rec.generate([tr("Seed", "Song")], radio_fn=radio)
        assert len(res["items"]) == 1

    def test_empty_radio(self):
        res = rec.generate([tr("Seed", "Song")], radio_fn=lambda s, l: [])
        assert res == {"items": [], "seeds": 1, "library_count": 1, "total": 0}

    def test_empty_library(self):
        res = rec.generate([], radio_fn=lambda s, l: [])
        assert res == {"items": [], "seeds": 0, "library_count": 0, "total": 0}

    def test_radio_error_skipped(self):
        def failing(seed, limit):
            raise RuntimeError("сеть")

        res = rec.generate([tr("Seed", "Song")], radio_fn=failing)
        assert res["items"] == []
        assert res["seeds"] == 1

    def test_candidate_carries_seed_label(self):
        records = [tr("SeedArtist", "Song")]
        radio, _, _ = self._radio([cand("Candidate", "OtherArtist")])
        res = rec.generate(records, radio_fn=radio)
        assert res["items"][0]["seed"] == "SeedArtist — Song"


class TestIterGenerate:
    """iter_generate: накопительный snapshot после каждого сида, логика та же."""

    def test_two_seeds_two_snapshots_in_order(self):
        """Два сида обрабатываются последовательно — snapshot после каждого."""
        calls = []

        def radio(seed, limit):
            calls.append(seed["artist"])
            return [cand(f"C-{seed['artist']}", "Other", f"v-{seed['artist']}")]

        snaps = list(rec.iter_generate([tr("A", "SongA"), tr("B", "SongB")],
                                       radio_fn=radio, rng=random.Random(0)))
        assert len(snaps) == 2
        assert [s["seed_index"] for s in snaps] == [1, 2]
        # radio зовётся по одному сиду за snapshot, в порядке снапшотов.
        assert [s["seed"].split(" — ")[0] for s in snaps] == calls
        for s in snaps:
            assert s["seed_count"] == 2
            assert s["seeds"] == 2
            assert s["library_count"] == 2
        # items накопительные.
        assert [s["total"] for s in snaps] == [1, 2]

    def test_snapshot_shape(self):
        """Точный набор полей snapshot по контракту."""
        snaps = list(rec.iter_generate([tr("A", "SongA")],
                                       radio_fn=lambda s, l: [cand("Cand", "Other")]))
        assert len(snaps) == 1
        assert set(snaps[0]) == {"seed_index", "seed_count", "seed", "items",
                                 "seeds", "library_count", "total"}

    def test_first_snapshot_before_second_radio_call(self):
        """Первый snapshot доступен до вызова radio второго сида (стриминг)."""
        calls = []

        def radio(seed, limit):
            calls.append(seed["artist"])
            return [cand("Cand", "Other", f"v-{seed['artist']}")]

        it = rec.iter_generate([tr("A", "SongA"), tr("B", "SongB")],
                               radio_fn=radio, rng=random.Random(0))
        snap1 = next(it)
        assert len(calls) == 1
        assert snap1["seed_index"] == 1
        assert snap1["seed_count"] == 2
        assert snap1["total"] == 1
        snap2 = next(it)
        assert len(calls) == 2
        assert snap2["seed_index"] == 2
        with pytest.raises(StopIteration):
            next(it)

    def test_cumulative_round_robin(self):
        """После 1-го сида — его группа; после 2-го — round-robin по обеим."""
        tracks = {
            "A": [cand("A1", "X", "va1"), cand("A2", "X", "va2")],
            "B": [cand("B1", "Y", "vb1"), cand("B2", "Y", "vb2")],
        }

        def radio(seed, limit):
            return tracks[seed["artist"]]

        snaps = list(rec.iter_generate([tr("A", "SongA"), tr("B", "SongB")],
                                       radio_fn=radio, rng=random.Random(7)))
        first = snaps[0]["seed"].split(" — ")[0]
        assert snaps[0]["total"] == 2
        assert [i["title"] for i in snaps[0]["items"]] == [f"{first}1", f"{first}2"]
        final = snaps[1]["items"]
        assert snaps[1]["total"] == 4
        assert sorted(i["title"] for i in final) == ["A1", "A2", "B1", "B2"]
        # Первые два кандидата — от разных сидов (round-robin).
        assert final[0]["seed"] != final[1]["seed"]

    def test_final_snapshot_matches_generate(self):
        """Итог round-robin прежний: последний snapshot == DTO generate."""
        tracks = {
            "A": [cand("A1", "X", "va1"), cand("A2", "X", "va2")],
            "B": [cand("B1", "Y", "vb1"), cand("B2", "Y", "vb2")],
            "C": [cand("C1", "Z", "vc1")],
        }

        def radio(seed, limit):
            return tracks[seed["artist"]]

        records = [tr(a, f"Song{a}") for a in "ABC"]
        gen = rec.generate(records, radio_fn=radio, rng=random.Random(11))
        snaps = list(rec.iter_generate(records, radio_fn=radio,
                                       rng=random.Random(11)))
        assert len(snaps) == 3
        assert snaps[-1]["items"] == gen["items"]
        assert (snaps[-1]["seeds"], snaps[-1]["library_count"],
                snaps[-1]["total"]) == (3, 3, 5)
        # Финальный DTO — только прежние ключи, без метаданных сида.
        assert set(gen) == {"items", "seeds", "library_count", "total"}
        assert (gen["seeds"], gen["library_count"], gen["total"]) == (3, 3, 5)

    def test_empty_radio_still_yields_snapshot(self):
        """Пустой результат радио — тоже один snapshot."""
        snaps = list(rec.iter_generate([tr("Seed", "Song")],
                                       radio_fn=lambda s, l: []))
        assert len(snaps) == 1
        snap = snaps[0]
        assert snap["seed_index"] == 1
        assert snap["seed_count"] == 1
        assert snap["seed"] == "Seed — Song"
        assert snap["items"] == []
        assert snap["seeds"] == 1
        assert snap["library_count"] == 1
        assert snap["total"] == 0

    def test_radio_error_yields_snapshot_and_next_seed_continues(self):
        """Исключение радио даёт snapshot и не мешает следующему сиду."""
        calls = []

        def radio(seed, limit):
            calls.append(seed["artist"])
            if len(calls) == 1:
                raise RuntimeError("сеть")
            return [cand("Ok", "Other", "v-ok")]

        records = [tr("A", "SongA"), tr("B", "SongB")]
        snaps = list(rec.iter_generate(records, radio_fn=radio,
                                       rng=random.Random(3)))
        assert len(snaps) == 2
        assert snaps[0]["seed"].startswith(f"{calls[0]} — ")
        assert snaps[0]["items"] == []
        assert snaps[0]["total"] == 0
        assert [i["title"] for i in snaps[1]["items"]] == ["Ok"]
        assert snaps[1]["total"] == 1

    def test_zero_seeds_no_snapshots(self):
        """Ноль сидов — ноль snapshots; generate возвращает прежний пустой DTO."""
        assert list(rec.iter_generate([], radio_fn=lambda s, l: [])) == []
        assert rec.generate([], radio_fn=lambda s, l: []) == {
            "items": [], "seeds": 0, "library_count": 0, "total": 0,
        }