import pytest

from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.interfaces import ProjectLocator
from thanhtan.projectlocator import EnvironmentProjectLocator, remember_project, user_dir
from thanhtan.workspace import init_workspace


@pytest.fixture
def project(gitflow_repo, workflow_file):
    init_workspace(gitflow_repo, workflow_file)
    return gitflow_repo


def locator(cwd, tmp_path, **env):
    home = tmp_path / "home"
    return EnvironmentProjectLocator(lambda: cwd, {**env, "THANHTAN_HOME": str(home)})


def test_it_implements_the_protocol(tmp_path):
    assert isinstance(locator(tmp_path, tmp_path), ProjectLocator)


def test_the_working_directory_wins(project, tmp_path):
    assert locator(project, tmp_path).find().root == project


def test_a_subdirectory_of_the_project_is_found_through_git(project, tmp_path):
    inner = project / "deep" / "er"
    inner.mkdir(parents=True)
    assert locator(inner, tmp_path).find().root == project


def test_the_project_dir_variable_is_next(project, tmp_path):
    elsewhere = tmp_path / "plugin-dir"
    elsewhere.mkdir()
    assert locator(elsewhere, tmp_path, THANHTAN_PROJECT_DIR=str(project)).find().root == project


def test_pwd_of_the_launching_shell_is_next(project, tmp_path):
    elsewhere = tmp_path / "plugin-dir"
    elsewhere.mkdir()
    assert locator(elsewhere, tmp_path, PWD=str(project)).find().root == project


def test_the_remembered_project_is_the_last_resort(project, tmp_path):
    elsewhere = tmp_path / "plugin-dir"
    elsewhere.mkdir()
    found = locator(elsewhere, tmp_path)
    with pytest.raises(ThanhTanError) as exc:
        found.find()
    assert exc.value.code is ExitCode.NO_WORKSPACE
    remember_project(project, {"THANHTAN_HOME": str(tmp_path / "home")})
    assert found.find().root == project


def test_a_remembered_project_that_lost_its_workspace_is_ignored(project, tmp_path):
    elsewhere = tmp_path / "plugin-dir"
    elsewhere.mkdir()
    remember_project(tmp_path / "gone", {"THANHTAN_HOME": str(tmp_path / "home")})
    with pytest.raises(ThanhTanError):
        locator(elsewhere, tmp_path).find()


def test_remembering_the_same_project_twice_does_not_rewrite(project, tmp_path):
    env = {"THANHTAN_HOME": str(tmp_path / "home")}
    remember_project(project, env)
    pointer = user_dir(env) / "active-project.txt"
    first = pointer.stat().st_mtime_ns
    remember_project(project, env)
    assert pointer.stat().st_mtime_ns == first and pointer.read_text(encoding="utf-8").strip() == str(project)


def test_the_error_lists_where_it_looked(tmp_path):
    with pytest.raises(ThanhTanError) as exc:
        locator(tmp_path, tmp_path, THANHTAN_PROJECT_DIR=str(tmp_path / "nowhere")).find()
    assert str(tmp_path / "nowhere") in str(exc.value) and "thanhtan init" in str(exc.value)
