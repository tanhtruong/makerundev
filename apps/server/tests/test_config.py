from makerundev_server import config


def test_new_variable_wins_over_the_old_name_and_the_default(monkeypatch):
    monkeypatch.delenv("MAKERUNDEV_PORT", raising=False)
    monkeypatch.delenv("PACELAB_PORT", raising=False)
    assert config.env("PORT", "8000") == "8000"

    monkeypatch.setenv("PACELAB_PORT", "9000")
    assert config.env("PORT", "8000") == "9000"

    monkeypatch.setenv("MAKERUNDEV_PORT", "9500")
    assert config.env("PORT", "8000") == "9500"


def test_data_directory_from_before_the_rename_keeps_its_database(tmp_path):
    assert config.database_path(tmp_path) == tmp_path / "makerundev.db"

    (tmp_path / "pacelab.db").touch()
    assert config.database_path(tmp_path) == tmp_path / "pacelab.db"

    (tmp_path / "makerundev.db").touch()
    assert config.database_path(tmp_path) == tmp_path / "makerundev.db"
