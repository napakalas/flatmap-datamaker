import os
import urllib.request
import zipfile
import io
from urllib.parse import urlparse
import re
from json import JSONDecodeError
import requests

def get_list_of_folder(directory):
    files_and_folders = os.listdir(directory)
    folders = [folder for folder in files_and_folders if os.path.isdir(os.path.join(directory, folder))]
    return folders

def extract_url_zip(url, destination):
    with urllib.request.urlopen(url) as response:
        zip_bytes = io.BytesIO(response.read())
    with zipfile.ZipFile(zip_bytes, 'r') as zip_ref:
        zip_ref.extractall(destination)

def is_url(string):
    parsed_url = urlparse(string)
    return parsed_url.scheme != '' and parsed_url.netloc != ''

def is_file_path(string):
    parsed_url = urlparse(string)
    return parsed_url.scheme == '' and parsed_url.netloc == ''

# these should be a temporary functions
def get_mapmaker_version(logfile):
    with open(logfile, 'r') as f:
        for line in f:
            if 'Mapmaker' in line:
                return line[line.index('Mapmaker'):].strip()

def get_mapknowledge_version(logfile):
    with open(logfile, 'r') as f:
        for line in f:
            if 'Map Knowledge version' in line:
                pattern = r"version (\d+\.\d+\.\d+)"
                match = re.search(pattern, line)
                if match:
                    return 'Map Knowledge ' + match.group(1)

#===============================================================================

SCICRUNCH_API_ENDPOINT = 'https://scicrunch.org/api/1'

#===============================================================================

# Values for SCICRUNCH_RELEASE
SCICRUNCH_PRODUCTION = 'sckan-scigraph'
SCICRUNCH_STAGING = 'sparc-scigraph'

#===============================================================================

SCICRUNCH_SPARC_API = '{API_ENDPOINT}/{SCICRUNCH_RELEASE}'
SCICRUNCH_SPARC_CYPHER = f'{SCICRUNCH_SPARC_API}/cypher/execute.json'
LOOKUP_TIMEOUT = 30    # seconds; for `requests.get()`

#===============================================================================

def get_sckan_version(scicrunch_release=SCICRUNCH_PRODUCTION):
    scicrunch_key = os.environ.get('SCICRUNCH_API_KEY')
    if scicrunch_key is not None:
            params = {
                'api_key': scicrunch_key,
                'limit': 9999,
            }
            params['cypherQuery'] = """MATCH
                                    (p)-[i:build:id]-(),
                                    (p)-[e]-()
                                    RETURN i, e"""
            data = request_json(SCICRUNCH_SPARC_CYPHER.format(API_ENDPOINT=SCICRUNCH_API_ENDPOINT,
                                                              SCICRUNCH_RELEASE=scicrunch_release),
                                params=params)
            for node in data['nodes']:
                if node['id'] == 'build:prov':
                    return 'SCKAN ' + node['meta']['http://uri.interlex.org/tgbugs/uris/readable/build/date'][0]
    return ''

#===============================================================================

def request_json(endpoint, **kwds):
    try:
        response = requests.get(endpoint,
                                headers={'Accept': 'application/json'},
                                timeout=LOOKUP_TIMEOUT,
                                **kwds)
        if response.status_code == requests.codes.ok:
            try:
                return response.json()
            except JSONDecodeError:
                error = 'Invalid JSON returned'
        else:
            error = response.reason
    except requests.exceptions.RequestException as exception:
        error = f'Exception: {exception}'
    return None

#===============================================================================
