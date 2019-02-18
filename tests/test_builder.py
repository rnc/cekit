import glob
import os
import subprocess
import yaml

try:
    from unittest.mock import call
except ImportError:
    from mock import call

from cekit.builder import Builder


def test_osbs_builder_defaults(mocker):
    mocker.patch.object(subprocess, 'check_output')

    builder = Builder('osbs', 'tmp', {})

    assert builder._release is False
    assert builder._fedpkg == 'fedpkg'
    assert builder._koji == 'koji'
    assert builder._koji_url == 'https://koji.fedoraproject.org/koji'
    assert builder._nowait is False


def test_osbs_builder_redhat(mocker):
    mocker.patch.object(subprocess, 'check_output')

    builder = Builder('osbs', 'tmp', {'redhat': True})

    assert builder._fedpkg == 'rhpkg'
    assert builder._koji == 'brew'
    assert builder._koji_url == 'https://brewweb.engineering.redhat.com/brew'


def test_osbs_builder_use_rhpkg_staget(mocker):
    mocker.patch.object(subprocess, 'check_output')

    params = {'stage': True,
              'redhat': True}
    builder = Builder('osbs', 'tmp', params)

    assert builder._fedpkg == 'rhpkg-stage'
    assert builder._koji == 'brew-stage'
    assert builder._koji_url == 'https://brewweb.stage.engineering.redhat.com/brew'


def test_osbs_builder_custom_commit_msg(mocker):
    mocker.patch.object(subprocess, 'check_output')

    params = {'stage': True,
              'commit_msg': 'foo'}
    builder = Builder('osbs', 'tmp', params)

    assert builder._commit_msg == 'foo'


def test_osbs_builder_nowait(mocker):
    mocker.patch.object(subprocess, 'check_output')

    params = {'nowait': True}
    builder = Builder('osbs', 'tmp', params)

    assert builder._nowait is True


def test_osbs_builder_user(mocker):
    mocker.patch.object(subprocess, 'check_output')

    params = {'user': 'UserFoo'}
    builder = Builder('osbs', 'tmp', params)

    assert builder._user == 'UserFoo'


def test_merge_container_yaml_no_limit_arch(mocker, tmpdir):
    mocker.patch.object(glob, 'glob', return_value=False)
    mocker.patch.object(subprocess, 'check_output')

    builder = Builder('osbs', 'tmp', {})
    builder.dist_git_dir = str(tmpdir.mkdir('target'))

    container_yaml_f = 'container.yaml'

    source = 'souce_cont.yaml'
    with open(source, 'w') as file_:
        yaml.dump({'tags': ['foo']}, file_)

    builder._merge_container_yaml(source, container_yaml_f)

    with open(container_yaml_f, 'r') as file_:
        container_yaml = yaml.safe_load(file_)
    os.remove(container_yaml_f)
    os.remove(source)

    assert 'paltforms' not in container_yaml


def test_merge_container_yaml_limit_arch(mocker, tmpdir):
    mocker.patch.object(glob, 'glob', return_value=True)
    mocker.patch.object(subprocess, 'check_output')
    builder = Builder('osbs', 'tmp', {})
    builder.dist_git_dir = str(tmpdir.mkdir('target'))

    container_yaml_f = 'container.yaml'

    source = 'souce_cont.yaml'
    with open(source, 'w') as file_:
        yaml.dump({'tags': ['foo']}, file_)

    builder._merge_container_yaml(source, container_yaml_f)

    with open(container_yaml_f, 'r') as file_:
        container_yaml = yaml.safe_load(file_)
    os.remove(container_yaml_f)
    os.remove(source)

    assert 'x86_64' in container_yaml['platforms']['only']
    assert len(container_yaml['platforms']['only']) == 1


class DistGitMock(object):
    def add(self):
        pass

    def stage_modified(self):
        pass


def create_osbs_build_object(mocker, builder_type, params={}):
    mocker.patch('cekit.tools.decision')

    builder = Builder(builder_type, 'tmp', params)
    builder.dist_git_dir = '/tmp'
    builder.dist_git = DistGitMock()
    builder.artifacts = []
    return builder


def test_osbs_builder_run_brew_stage(mocker):
    params = {'stage': True,
              'redhat': True}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    check_output.assert_has_calls([
        call(['git', 'remote', 'get-url', 'origin']),
        call(['git', 'rev-parse', 'HEAD']),
        call(['brew-stage', 'call', '--python', 'buildContainer', '--kwargs',
              "{'src': 'git://something.redhat.com/containers/openjdk#c5a0731b558c8a247dd7f85b5f54462cd5b68b23', 'target': 'some-branch-containers-candidate', 'opts': {'scratch': True, 'git_branch': 'some-branch', 'yum_repourls': []}}"])
    ])

    builder._wait_for_osbs_task.assert_called_once_with('12345')


def test_osbs_builder_run_brew(mocker):
    params = {'redhat': True}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    check_output.assert_has_calls([
        call(['git', 'remote', 'get-url', 'origin']),
        call(['git', 'rev-parse', 'HEAD']),
        call(['brew', 'call', '--python', 'buildContainer', '--kwargs',
              "{'src': 'git://something.redhat.com/containers/openjdk#c5a0731b558c8a247dd7f85b5f54462cd5b68b23', 'target': 'some-branch-containers-candidate', 'opts': {'scratch': True, 'git_branch': 'some-branch', 'yum_repourls': []}}"])
    ])

    builder._wait_for_osbs_task.assert_called_once_with('12345')


def test_osbs_builder_run_koji(mocker):
    params = {'redhat': False}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    check_output.assert_has_calls([
        call(['git', 'remote', 'get-url', 'origin']),
        call(['git', 'rev-parse', 'HEAD']),
        call(['koji', 'call', '--python', 'buildContainer', '--kwargs',
              "{'src': 'git://something.redhat.com/containers/openjdk#c5a0731b558c8a247dd7f85b5f54462cd5b68b23', 'target': 'some-branch-containers-candidate', 'opts': {'scratch': True, 'git_branch': 'some-branch', 'yum_repourls': []}}"])
    ])

    builder._wait_for_osbs_task.assert_called_once_with('12345')


def test_osbs_builder_run_brew_nowait(mocker):
    params = {'nowait': True,
              'redhat': True}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    builder._wait_for_osbs_task.assert_not_called()


def test_osbs_builder_run_brew_user(mocker):
    params = {'user': 'Foo',
              'redhat': True}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    check_output.assert_called_with(['brew', '--user', 'Foo', 'call', '--python', 'buildContainer', '--kwargs',
                                     "{'src': 'git://something.redhat.com/containers/openjdk#c5a0731b558c8a247dd7f85b5f54462cd5b68b23', 'target': 'some-branch-containers-candidate', 'opts': {'scratch': True, 'git_branch': 'some-branch', 'yum_repourls': []}}"])


def test_osbs_builder_run_brew_target(mocker):
    params = {'target': 'Foo',
              'redhat': True}

    check_output = mocker.patch.object(subprocess, 'check_output', autospec=True, side_effect=[
                                       b'ssh://user:password@something.redhat.com/containers/openjdk', b'c5a0731b558c8a247dd7f85b5f54462cd5b68b23', b'12345'])
    builder = create_osbs_build_object(mocker, 'osbs', params)
    mocker.patch.object(builder, '_wait_for_osbs_task')
    builder.dist_git.branch = "some-branch"
    builder.build()

    check_output.assert_called_with(['brew', 'call', '--python', 'buildContainer', '--kwargs',
                                     "{'src': 'git://something.redhat.com/containers/openjdk#c5a0731b558c8a247dd7f85b5f54462cd5b68b23', 'target': 'Foo', 'opts': {'scratch': True, 'git_branch': 'some-branch', 'yum_repourls': []}}"])


def test_docker_builder_defaults():
    params = {'tags': ['foo', 'bar']}
    builder = Builder('docker', 'tmp', params)

    assert builder._tags == ['foo', 'bar']


def test_buildah_builder_run(mocker):
    params = {'tags': ['foo', 'bar']}
    check_call = mocker.patch.object(subprocess, 'check_call')
    builder = create_osbs_build_object(mocker, 'buildah', params)
    builder.build()

    check_call.assert_called_once_with(['sudo',
                                        'buildah',
                                        'build-using-dockerfile',
                                        '-t', 'foo',
                                        '-t', 'bar',
                                        'tmp/image'])


def test_buildah_builder_run_pull(mocker):
    params = {'tags': ['foo', 'bar'], 'pull': True}
    check_call = mocker.patch.object(subprocess, 'check_call')
    builder = create_osbs_build_object(mocker, 'buildah', params)
    builder.build()

    check_call.assert_called_once_with(['sudo',
                                        'buildah',
                                        'build-using-dockerfile',
                                        '--pull-always',
                                        '-t', 'foo',
                                        '-t', 'bar',
                                        'tmp/image'])
