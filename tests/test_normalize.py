"""Tests for src/normalize.py — normalization planning and application."""
from __future__ import annotations

from pathlib import Path

from src.normalize import (
    NormalizationPlan,
    plan_normalizations,
    plan_global_genre_normalizations,
    normalize_library,
    normalize_global_genres,
    apply_plan,
    _clean_whitespace,
    _normalize_feat,
    _clean_track_num,
    _canonical_genre,
)
from src.analytics import TrackRecord


def _rec(
    path: str = "a.mp3",
    artist: str = "Artist",
    album: str = "Album",
    title: str = "Song",
    year: str = "2020",
    genre: str = "Rock",
    album_artist: str = "",
    track_number: str = "",
    disc_number: str = "",
) -> TrackRecord:
    return TrackRecord(
        path=Path(path),
        artist=artist,
        album=album,
        title=title,
        year=year,
        genre=genre,
        album_artist=album_artist,
        track_number=track_number,
        disc_number=disc_number,
    )


def _changes(plan: NormalizationPlan, field: str, path: str | None = None):
    return [
        c for c in plan.changes
        if c.field == field and (path is None or str(c.path) == path)
    ]


class TestTransformers:
    def test_whitespace(self):
        assert _clean_whitespace("  A  B  ") == "A B"
        assert _clean_whitespace("A\xa0B") == "A B"

    def test_feat_variants(self):
        assert _normalize_feat("A ft. B") == "A feat. B"
        assert _normalize_feat("A featuring B") == "A feat. B"
        assert _normalize_feat("A (ft B)") == "A (feat. B)"
        assert _normalize_feat("A feat. B") == "A feat. B"
        assert _normalize_feat("Nothing to see") == "Nothing to see"
        assert _normalize_feat("Stand Here With Me") == "Stand Here With Me"

    def test_track_num(self):
        assert _clean_track_num("01") == "1"
        assert _clean_track_num(" 07 ") == "7"


class TestPlanNormalizations:
    def test_empty(self):
        plan = plan_normalizations([])
        assert plan.count == 0

    def test_clean_unchanged(self):
        records = [
            _rec("a.mp3", artist="Pink Floyd", album="Dark Side", title="Time",
                 genre="Rock", year="1973", track_number="1"),
            _rec("b.mp3", artist="Pink Floyd", album="Dark Side", title="Money",
                 genre="Rock", year="1973", track_number="2"),
        ]
        assert plan_normalizations(records).count == 0

    def test_whitespace_planning(self):
        records = [_rec("a.mp3", artist="Artist ", album="Album")]
        plan = plan_normalizations(records)
        assert _changes(plan, "artist")
        assert _changes(plan, "artist")[0].old_value == "Artist "
        assert _changes(plan, "artist")[0].new_value == "Artist"

    def test_feat_planning(self):
        records = [_rec("a.mp3", title="A ft. B")]
        plan = plan_normalizations(records)
        ch = _changes(plan, "title")
        assert ch and ch[0].new_value == "A feat. B"

    def test_tracknum_planning(self):
        records = [_rec("a.mp3", track_number="01")]
        plan = plan_normalizations(records)
        ch = _changes(plan, "track_number")
        assert ch and ch[0].new_value == "1"

    def test_artist_case_alignment(self):
        records = [
            _rec("a.mp3", artist="Pink Floyd", album="X"),
            _rec("b.mp3", artist="Pink Floyd", album="Y"),
            _rec("c.mp3", artist="pink floyd", album="Z"),
        ]
        plan = plan_normalizations(records)
        ch = _changes(plan, "artist", "c.mp3")
        assert ch and ch[0].new_value == "Pink Floyd"

    def test_genre_alignment(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", genre="Rock"),
            _rec("b.mp3", artist="A", album="Alb", genre="Pop"),
        ]
        plan = plan_normalizations(records)
        # оба совпадут с самым частым — либо одним, либо другим (при равенстве)
        assert len(_changes(plan, "genre")) == 1

    def test_no_fill_empty_genre(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", genre="Rock"),
            _rec("b.mp3", artist="A", album="Alb", genre=""),
        ]
        # пустой жанр не заполняем навязчиво
        assert len(_changes(plan_normalizations(records), "genre")) == 0


class TestApply:
    def test_apply_renames_fields(self, tmp_path):
        from src.tagger import AudioTags, set_tags, get_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="A ft. B", artist="artist", album="Album"))
        records = [_rec(str(p), artist="artist", album="Album", title="A ft. B")]
        plan = plan_normalizations(records)
        # применяем по фактическим тегам на диске
        applied, errors = apply_plan(plan)
        assert applied == 1
        assert errors == 0
        tags = get_tags(p)
        assert tags.title == "A feat. B"
        assert tags.artist == "artist"  # регистр: один вариант — не меняем

    def test_apply_plan_filter_by_cause(self, tmp_path):
        from src.tagger import AudioTags, set_tags, get_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="A ft. B", artist="Artist ", album="X"))
        records = [_rec(str(p), artist="Artist ", album="X", title="A ft. B")]
        plan = plan_normalizations(records)
        assert set(c.cause for c in plan.changes) >= {"feat", "whitespace"}

        # применяем только фиты — whitespace остаётся на диске
        applied, errors = apply_plan(plan, causes=["feat"])
        assert applied == 1 and errors == 0
        tags = get_tags(p)
        assert tags.title == "A feat. B"
        assert tags.artist == "Artist "  # хвостовой пробел не тронут

        # несуществующая причина — план пуст
        applied, errors = apply_plan(plan, causes=["nope"])
        assert applied == 0 and errors == 0

    def test_normalize_library(self, tmp_path):
        from src.tagger import AudioTags, set_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="Song", artist="Artist ", album="X"))
        plan = normalize_library(tmp_path)
        assert plan.count == 1
        assert plan.changes[0].field == "artist"


class TestGlobalGenreNormalization:
    def test_canonical_genre_maps_synonyms(self):
        assert _canonical_genre("Rap/Hip Hop") == "Хип-хоп"
        assert _canonical_genre("Рэп") == "Хип-хоп"
        assert _canonical_genre("Альтернативная музыка") == "Альтернатива"

    def test_canonical_genre_unchanged(self):
        assert _canonical_genre("Хип-хоп") is None
        assert _canonical_genre("Поп") is None

    def test_plan_global_genres(self):
        records = [
            _rec("a.mp3", genre="Rap/Hip Hop"),
            _rec("b.mp3", genre="Хип-хоп"),
            _rec("c.mp3", genre="Поп"),
        ]
        plan = plan_global_genre_normalizations(records)
        assert len(plan.changes) == 1
        ch = plan.changes[0]
        assert ch.field == "genre"
        assert ch.old_value == "Rap/Hip Hop"
        assert ch.new_value == "Хип-хоп"

    def test_plan_global_genres_custom_mapping(self):
        records = [_rec("a.mp3", genre="Indie")]
        plan = plan_global_genre_normalizations(
            records, mapping={"indie": "Инди"}
        )
        assert len(plan.changes) == 1
        assert plan.changes[0].new_value == "Инди"

    def test_normalize_global_genres_library(self, tmp_path):
        from src.tagger import AudioTags, set_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="Song", artist="Artist", album="X", genre="Рэп"))
        plan = normalize_global_genres(tmp_path)
        assert plan.count == 1
        assert plan.changes[0].new_value == "Хип-хоп"
