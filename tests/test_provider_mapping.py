from letterboxd_recs.availability import provider_column_from_arg


def test_provider_column_aliases() -> None:
    assert provider_column_from_arg("netflix") == "netflix"
    assert provider_column_from_arg("apple-itunes") == "apple_itunes"
    assert provider_column_from_arg("amazonprimevideo") == "prime_video"
    assert provider_column_from_arg("source-google-play-movies") == "google_play_movies"
    assert provider_column_from_arg("unknown-service") is None
