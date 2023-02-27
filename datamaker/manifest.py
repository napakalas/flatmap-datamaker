from __future__ import annotations
import uuid
import urllib
import pathlib
from urllib.parse import urljoin, urlparse
import logging as log
import os
import io
import json
from typing import Optional
from enum import Enum
import urllib.request

#===============================================================================

import git
import giturlparse

#===============================================================================

GITHUB_GIT_HOST = 'github.com'
PHYSIOMEPROJECT_GIT_HOST = 'physiomeproject.org'

#===============================================================================

class GitState(Enum):
    UNKNOWN   = 0
    DONTCARE  = 1
    STAGED    = 2
    CHANGED   = 3
    UNTRACKED = 4

#===============================================================================

def relative_path(path: str | pathlib.Path) -> bool:
    return str(path).split(':', 1)[0] not in ['file', 'http', 'https']

def make_uri(path: str | pathlib.Path) -> str:
    return pathlib.Path(os.path.abspath(path)).as_uri() if relative_path(path) else str(path)

def pathlib_path(path: str) -> pathlib.Path:
    return pathlib.Path(urlparse(path).path)

#===============================================================================

class FilePathError(IOError):
    pass

#===============================================================================

class MapRepository:
    def __init__(self, working_dir: pathlib.Path):
        try:
            self.__repo = git.Repo(working_dir, search_parent_directories=True)     # type:ignore
            self.__repo_path = pathlib.Path(self.__repo.working_dir).absolute()     # type:ignore
            self.__changed_items = [ item.a_path for item in self.__repo.index.diff(None) ]
            self.__staged_items = [ item.a_path for item in self.__repo.index.diff('HEAD') ]
            self.__untracked_files = self.__repo.untracked_files
            self.__upstream_base = self.__get_upstream_base()
        except git.InvalidGitRepositoryError:
            raise ValueError("Flatmap sources must be in a git managed directory ('--authoring' or '--ignore-git' option intended?)")

    @property
    def remotes(self) -> dict[str, str]:
        return {
            remote.name: giturlparse.parse(remote.url).url2https
                for remote in self.__repo.remotes
            }

    @property
    def sha(self) -> str:
        return self.__repo.head.commit.hexsha

    def __git_path(self, path):
        if self.__repo is not None:
            if path.startswith('file://'):
                path = path[7:]
            full_path = pathlib.Path(os.path.abspath(path))
            if full_path.is_relative_to(self.__repo_path):
                return str(full_path.relative_to(self.__repo_path))

    def __get_upstream_base(self) -> Optional[str]:
        url = None
        for remote in self.__repo.remotes:
            https_url = giturlparse.parse(remote.url).url2https
            url = giturlparse.parse(https_url)
            if (url.host.endswith(GITHUB_GIT_HOST)
             or url.host.endswith(PHYSIOMEPROJECT_GIT_HOST)):
                break
        if url is not None:
            raw_folder = ('blob/' if url.host.endswith(GITHUB_GIT_HOST) else
                          'rawfile/' if url.host.endswith(PHYSIOMEPROJECT_GIT_HOST) else
                          '')
            return f'{url.protocol}://{url.host}{url.port}/{url.owner}/{url.repo}/{raw_folder}{self.__repo.head.commit.hexsha}/'  # type: ignore

    def status(self, path: str) -> GitState:
    #=======================================
        if (git_path := self.__git_path(path)) is not None:
            return (GitState.UNTRACKED if git_path in self.__untracked_files else
                    GitState.CHANGED if git_path in self.__changed_items else
                    GitState.STAGED if git_path in self.__staged_items else
                    GitState.DONTCARE)
        else:
            log.warning(f"{path} is not under git control in the manifest's directory")
        return GitState.UNKNOWN

    def path_blob_url(self, path):
    #=============================
        if (git_path := self.__git_path(path)) is not None:
            return urljoin(self.__upstream_base, git_path)

#===============================================================================
class Manifest:
    def __init__(self, manifest_path, single_file=None, id=None, ignore_git=False):
        self.__path = FilePath(manifest_path)
        if not ignore_git:
            self.__repo = MapRepository(pathlib.Path(manifest_path).parent)
        self.__ignore_git = ignore_git
        self.__url = self.__path.url
        self.__connections = {}
        self.__connectivity = []
        self.__neuron_connectivity = []
        self.__uncommitted = 0

        if single_file is not None:
            # A special case is to make a map from a standalone source file
            if id is None:
                id = self.__url.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('_', '-').replace(' ', '_')
            self.__manifest = {
                'id': id,
                'sources': [
                    {
                        'id': id,
                        'href': self.__url,
                        'kind': 'base' if single_file == 'svg' else single_file
                    }
                ]
            }
        else:
            # Check the manifest itself is committed into the repository
            self.__check_committed(self.__url)

            self.__manifest = self.__path.get_json()
            if id is not None:
                self.__manifest['id'] = id
            elif 'id' not in self.__manifest:
                raise ValueError('No id given for manifest')

            if self.__manifest.get('sckan-version', 'production') not in ['production', 'staging']:
                raise ValueError("'sckan-version' in manifest must be `production' or 'staging'")
            for model in self.__manifest.get('neuronConnectivity', []):
                self.__neuron_connectivity.append(model)

            if 'sources' not in self.__manifest:
                raise ValueError('No sources given for manifest')
            for source in self.__manifest['sources']:
                source['href'] = self.__check_and_normalise_path(source['href'])
            if 'anatomicalMap' in self.__manifest:
                self.__manifest['anatomicalMap'] = self.__check_and_normalise_path(self.__manifest['anatomicalMap'])
            if 'annotation' in self.__manifest:
                self.__manifest['annotation'] = self.__check_and_normalise_path(self.__manifest['annotation'])
            if 'connectivityTerms' in self.__manifest:
                self.__manifest['connectivityTerms'] = self.__check_and_normalise_path(self.__manifest['connectivityTerms'])
            if 'properties' in self.__manifest:
                self.__manifest['properties'] = self.__check_and_normalise_path(self.__manifest['properties'])
            for path in self.__manifest.get('connectivity', []):
                self.__connectivity.append(self.__check_and_normalise_path(path))
            if not ignore_git and self.__uncommitted:
                raise TypeError("Not all of the flatmap's sources are commited into git ('--authoring' or '--ignore-git' option intended?)")

    @property
    def anatomical_map(self):
        return self.__manifest.get('anatomicalMap')

    @property
    def annotation(self):
        return self.__manifest.get('annotation')

    @property
    def biological_sex(self):
        return self.__manifest.get('biological-sex')

    @property
    def connections(self):
        return self.__connections

    @property
    def connectivity(self):
        return self.__connectivity

    @property
    def connectivity_terms(self):
        return self.__manifest.get('connectivityTerms')

    @property
    def git_status(self):
        if not self.__ignore_git and self.__repo.sha is not None:
            return {
                'sha': self.__repo.sha,
                'remotes': self.__repo.remotes
            }

    @property
    def id(self):
        return self.__manifest['id']

    @property
    def kind(self):
        return self.__manifest.get('kind', 'anatomical')

    @property
    def models(self):
        return self.__manifest.get('models')

    @property
    def neuron_connectivity(self):
        return self.__neuron_connectivity

    @property
    def properties(self):
        return self.__manifest.get('properties')

    @property
    def sckan_version(self):
        return self.__manifest.get('sckan-version', 'production')

    @property
    def sources(self):
        return self.__manifest['sources']

    @property
    def url(self):
        if (not self.__ignore_git
        and (blob_url := self.__repo.path_blob_url(self.__url)) is not None):
            return blob_url
        return self.__url

    @property
    def uuid(self):
        if not self.__ignore_git:
            return str(uuid.uuid5(uuid.NAMESPACE_URL,
                                  self.__repo.sha + json.dumps(self.__manifest)))

    def __check_and_normalise_path(self, path) -> str:
    #=================================================
        normalised_path = self.__path.join_url(path)
        if not self.__ignore_git:
            self.__check_committed(normalised_path)
        return normalised_path

    def __check_committed(self, path):
    #=================================
        if not self.__ignore_git:
            git_state = self.__repo.status(path)
            if git_state != GitState.DONTCARE:
                message = ('unknown to git' if git_state == GitState.UNKNOWN else
                           'staged to be committed' if git_state == GitState.STAGED else
                           'unstaged with changes' if git_state == GitState.CHANGED else
                           'untracked by git')
                log.error(f'{path} is {message}')
                self.__uncommitted += 1

#===============================================================================

class FilePath(object):
    def __init__(self, path: str):
        self.__url = make_uri(path)

    @property
    def extension(self) -> str:
        parts = self.filename.rsplit('.')
        return parts[-1] if len(parts) > 1 else ''

    @property
    def filename(self) -> str:
        return urlparse(self.__url).path.rsplit('/', 1)[-1]

    @property
    def url(self) -> str:
        return self.__url

    def __str__(self) -> str:
        return self.__url

    def get_data(self):
        with self.get_fp() as fp:
            return fp.read()

    def get_fp(self):
        try:
            return urllib.request.urlopen(self.__url)
        except urllib.error.URLError:
            raise FilePathError('Cannot open path: {}'.format(self.__url)) from None

    def get_json(self) -> Any:
        try:
            return json.loads(self.get_data())
        except json.JSONDecodeError as err:
            raise ValueError('{}: {}'.format(self.__url, err)) from None

    def get_BytesIO(self) -> io.BytesIO:
        bytesio = io.BytesIO(self.get_data())
        bytesio.seek(0)
        return bytesio

    def join_path(self, path):
        return FilePath(urljoin(self.__url, path))

    def join_url(self, path):
        return urljoin(self.__url, path)

#===============================================================================