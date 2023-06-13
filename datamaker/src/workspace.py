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

from datamaker.src.tools import is_url, is_file_path

#===============================================================================

class Workspace:
    def __init__(self, workspace, commit, ignore_git):
        if is_url(workspace):
            self.__directory = tempfile.TemporaryDirectory()
            self.__path = Path(self.__directory.name).resolve()
            self.repository = pygit2.clone_repository(workspace, self.__path)
        elif is_file_path(workspace):
            self.__directory = tempfile.TemporaryDirectory()
            self.__path = Path(workspace).resolve()
            self.repository = pygit2.Repository(workspace)
        
        commit_id = self.repository.revparse_single('HEAD' if commit==None else commit)
        self.repository.checkout_tree(commit_id,
            strategy=pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)
        self.repository.set_head(commit_id.id)
        self.__commit_times = {}
        last_commit = self.repository[self.repository.head.target]
        for commit in self.repository.walk(last_commit.id,
                pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_TOPOLOGICAL):
            tzinfo = timezone(timedelta(minutes=commit.author.offset))
            commit_time = datetime.fromtimestamp(float(commit.author.time), tzinfo)
            for file in commit.tree:
                if file.name not in self.__commit_times:
                    self.__commit_times[file.name] = commit_time
                elif not ignore_git:# check ignore_git
                    self.close()
                    raise Exception(f'{file.name} in {workspace} is not commited') from None
                    
    @property
    def path(self):
        return self.__path
    
    @property
    def generated_path(self):
        return Path(self.__directory.name).resolve()

    def close(self):
        del self.__directory
        self.__directory = None

    def last_commit_time(self, file_path):
        return self.__commit_times.get(str(file_path), '')
    
    def workspace_url(self):
        url = self.repository.remotes["origin"].url
        return url if url.startswith('https') else 'https://github.com/' + url.split(':')[-1]

#===============================================================================
