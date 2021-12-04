#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2020-2021  David Brooks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#===============================================================================

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

#===============================================================================

import pygit2

#===============================================================================

class Workspace:
    def __init__(self, workspace, commit):
        self.__directory = tempfile.TemporaryDirectory()
        self.__path = Path(self.__directory.name).resolve()
        self.__repository = pygit2.clone_repository(workspace, self.__path)
        commit_id = self.__repository.revparse_single(commit)
        self.__repository.checkout_tree(commit_id,
            strategy=pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)
        self.__repository.set_head(pygit2.Oid(hex=commit))
        self.__commit_times = {}
        last_commit = self.__repository[self.__repository.head.target]
        for commit in self.__repository.walk(last_commit.id,
                pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_TOPOLOGICAL):
            tzinfo = timezone(timedelta(minutes=commit.author.offset))
            commit_time = datetime.fromtimestamp(float(commit.author.time), tzinfo)
            seen_files = False
            for file in commit.tree:
                if file.name not in self.__commit_times:
                    self.__commit_times[file.name] = commit_time
                    seen_files = True
            if not seen_files:
                break

    @property
    def path(self):
        return self.__path

    def close(self):
        del self.__directory
        self.__directory = None

    def last_commit_time(self, file_path):
        return self.__commit_times.get(str(file_path), '')

#===============================================================================
