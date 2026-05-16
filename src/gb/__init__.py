from importlib.metadata import version

# Single source of truth: bump pyproject.toml, this picks it up via package metadata.
__version__ = version("githubbuddy")
