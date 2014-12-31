# This file is part of Flask-PluginEngine.
# Copyright (C) 2014 CERN
#
# Flask-PluginEngine is free software; you can redistribute it
# and/or modify it under the terms of the Revised BSD License.

from __future__ import unicode_literals

import os
import pkgutil
import sys
from functools import wraps

from ._compat import iteritems


def get_state(app):
    """Gets the application-specific plugine engine data."""
    assert 'pluginengine' in app.extensions, \
        'The pluginengine extension was not registered to the current application. ' \
        'Please make sure to call init_app() first.'
    return app.extensions['pluginengine']


def resolve_dependencies(plugins):
    """Resolves dependencies between plugins and sorts them accordingly.

    This function guarantees that a plugin is never loaded before any
    plugin it depends on. If multiple plugins are ready to be loaded,
    the order in which they are loaded is undefined and should not be
    relied upon. If you want a certain order, add a (soft) dependency!

    :param plugins: dict mapping plugin names to plugin classes
    """
    plugins_deps = {name: (cls.required_plugins, cls.used_plugins) for name, cls in iteritems(plugins)}
    resolved_deps = set()
    while plugins_deps:
        # Get plugins with both hard and soft dependencies being met
        ready = {cls for cls, deps in iteritems(plugins_deps) if all(d <= resolved_deps for d in deps)}
        if not ready:
            # Otherwise check for plugins with all hard dependencies being met
            ready = {cls for cls, deps in iteritems(plugins_deps) if deps[0] <= resolved_deps}
        if not ready:
            # Either a circular dependency or a dependency that's not loaded
            raise Exception('Could not resolve dependencies between plugins')
        resolved_deps |= ready
        for name in ready:
            yield name, plugins[name]
            del plugins_deps[name]


def make_hashable(obj):
    """Makes an object containing dicts and lists hashable."""
    if isinstance(obj, list):
        return tuple(obj)
    elif isinstance(obj, dict):
        return frozenset((k, make_hashable(v)) for k, v in iteritems(obj))
    return obj


# http://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_nested_functions
def memoize(obj):
    cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = (make_hashable(args), make_hashable(kwargs))
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]

    return memoizer


@memoize
def wrap_in_plugin_context(plugin, func):
    assert plugin is not None

    @wraps(func)
    def wrapped(*args, **kwargs):
        with plugin.plugin_context():
            return func(*args, **kwargs)

    return wrapped


def with_plugin_context(plugin):
    """Decorator to ensure a function is always called in the given plugin context.

    :param plugin: Plugin instance
    """
    def decorator(f):
        return wrap_in_plugin_context(plugin, f)

    return decorator


def trim_docstring(docstring):
    """Trims a docstring based on the algorithm in PEP 257

    http://legacy.python.org/dev/peps/pep-0257/#handling-docstring-indentation
    """
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def get_root_path(import_name):
    """Returns the path to a package or cwd if that cannot be found.  This
    returns the path of a package or the folder that contains a module.

    From: https://github.com/mitsuhiko/flask/blob/master/flask/helpers.py
    """
    # Module already imported and has a file attribute.  Use that first.
    mod = sys.modules.get(import_name)
    if mod is not None and hasattr(mod, '__file__'):
        return os.path.dirname(os.path.abspath(mod.__file__))

    # Next attempt: check the loader.
    loader = pkgutil.get_loader(import_name)

    # Loader does not exist or we're referring to an unloaded main module
    # or a main module without path (interactive sessions), go with the
    # current working directory.
    if loader is None or import_name == '__main__':
        return os.getcwd()

    # For .egg, zipimporter does not have get_filename until Python 2.7.
    # Some other loaders might exhibit the same behavior.
    if hasattr(loader, 'get_filename'):
        filepath = loader.get_filename(import_name)
    else:
        # Fall back to imports.
        __import__(import_name)
        filepath = sys.modules[import_name].__file__

    # filepath is import_name.py for a module, or __init__.py for a package.
    return os.path.dirname(os.path.abspath(filepath))
