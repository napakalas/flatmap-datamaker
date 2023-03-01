Installation::

    $ pip install https://github.com/dbrnz/flatmap-datamaker/releases/download/0.1.0/datamaker-0.1.0-py3-none-any.whl


Usage::

    $ mapdatamaker --help

    usage: mapdatamaker [-h] WORKSPACE COMMIT MANIFEST DATASET [VERSION]

    Create a SPARC Dataset of a flatmap's sources on PMR

    positional arguments:
      WORKSPACE   URL of a PMR workspace containing a flatmap manifest
      COMMIT      SHA of workspace commit to use for dataset
      MANIFEST    name of flatmap manifest in workspace
      DATASET     full mame for resulting dataset
      [VERSION]     version of dataset_description, optional -> empty will be the latest version

    optional arguments:
      -h, --help  show this help message and exit


Example::

    $ mapdatamaker \
             https://models.physiomeproject.org/workspace/62f \
             1018a30afc1a675fcc6aa504204a0652ca059dff \
             manifest.json \
             dataset.zip

    $ mapdatamaker \
             https://models.physiomeproject.org/workspace/62f \
             1018a30afc1a675fcc6aa504204a0652ca059dff \
             manifest.json \
             dataset.zip \
             2.1.0

    $ mapdatamaker \
             https://models.physiomeproject.org/workspace/62f \
             1018a30afc1a675fcc6aa504204a0652ca059dff \
             manifest.json \
             dataset.zip \
             1.2.3

To merge to mapmaker, need to modify the import statement

`https://github.com/napakalas/flatmap-datamaker/blob/main/datamaker/flatmap.py#L45-L47`

and

`https://github.com/napakalas/flatmap-datamaker/blob/main/datamaker/__main__.py#L32-L34`

We need to update data_mapping.json in the repo for a newly published version. The code, by default, will load the updated file.