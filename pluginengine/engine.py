# This file is part of Flask-PluginEngine.
# Copyright (C) 2014 CERN
#
# Flask-PluginEngine is free software; you can redistribute it
# and/or modify it under the terms of the Revised BSD License.

from __future__ import unicode_literals
from pkg_resources import iter_entry_points, get_distribution

from werkzeug.datastructures import ImmutableDict

from .plugin import Plugin
from .signals import plugins_loaded
from .util import resolve_dependencies, get_root_path
from .logging import create_logger


class PluginEngine(object):
    plugin_class = Plugin

    def __init__(self, namespace, logger=None):
        self._state = _PluginEngineState(self, logger)
        self.plugins_to_load = []
        self.plugins_namespace = namespace

    @property
    def state(self):
        return self._state

    def load_plugins(self, skip_failed=True):
        """Loads all plugins for an application.

        :param app: A Flask application
        :param skip_failed: If True, initialize plugins even if some
          plugins could not be loaded.
        :return: True if all plugins could have been loaded, False otherwise.
        """
        state = self.state
        if state.plugins_loaded:
            raise RuntimeError('Plugins already loaded')
        state.plugins_loaded = True
        plugins = self._import_plugins()
        if state.failed and not skip_failed:
            return False
        for name, cls in resolve_dependencies(plugins):
            instance = cls(self)
            state.plugins[name] = instance
        plugins_loaded.send()
        return not state.failed

    def _import_plugins(self):
        """Imports the plugins for an application.

        :param app: A Flask application
        :return: A dict mapping plugin names to plugin classes
        """
        state = self.state
        plugins = {}
        for name in self.plugins_to_load:
            entry_points = list(iter_entry_points(self.plugins_namespace, name))
            if not entry_points:
                state.logger.error('Plugin {} does not exist'.format(name))
                state.failed.add(name)
                continue
            elif len(entry_points) > 1:
                state.logger.error('Plugin name {} is not unique (defined in {})'
                                   .format(name, ', '.join(ep.module_name for ep in entry_points)))
                state.failed.add(name)
                continue
            entry_point = entry_points[0]
            try:
                plugin_class = entry_point.load()
            except ImportError:
                state.logger.exception('Could not load plugin {}'.format(name))
                state.failed.add(name)
                continue
            if not issubclass(plugin_class, self.plugin_class):
                state.logger.error('Plugin {} does not inherit from {}'.format(name, self.plugin_class.__name__))
                state.failed.add(name)
                continue
            plugin_class.package_name = entry_point.module_name.split('.')[0]
            plugin_class.package_version = get_distribution(plugin_class.package_name).version
            if plugin_class.version is None:
                plugin_class.version = plugin_class.package_version
            plugin_class.name = name
            plugin_class.root_path = get_root_path(entry_point.module_name)
            plugins[name] = plugin_class
        return plugins

    def get_failed_plugins(self):
        """Returns the list of plugins which could not be loaded.

        :param app: A Flask app. Defaults to the current app.
        """
        return frozenset(self.state.failed)

    def get_active_plugins(self):
        """Returns the currently active plugins.

        :param app: A Flask app. Defaults to the current app.
        :return: dict mapping plugin names to plugin instances
        """
        return ImmutableDict(self.state.plugins)

    def has_plugin(self, name):
        """Returns if a plugin is loaded in the current app.

        :param name: Plugin name
        :param app: A Flask app. Defaults to the current app.
        """
        return name in self.state.plugins

    def get_plugin(self, name):
        """Return a specific plugin of the current app.

        :param name: Plugin name
        :param app: A Flask app. Defaults to the current app.
        """
        return self.state.plugins.get(name)

    def __repr__(self):
        return '<PluginEngine()>'


class _PluginEngineState(object):
    def __init__(self, plugin_engine, logger=None):
        if logger is None:
            logger = create_logger(__name__)
        self.plugin_engine = plugin_engine
        self.logger = logger
        self.plugins = {}
        self.failed = set()
        self.plugins_loaded = False

    def __repr__(self):
        return '<_PluginEngineState({}, {})>'.format(self.plugin_engine, self.plugins)
