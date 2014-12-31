# This file is part of Flask-PluginEngine.
# Copyright (C) 2014 CERN
#
# Flask-PluginEngine is free software; you can redistribute it
# and/or modify it under the terms of the Revised BSD License.

from pkg_resources import EntryPoint, Distribution

import pytest
from pytest import raises

from pluginengine import PluginEngine, plugins_loaded, Plugin


class EspressoModule(Plugin):
    """EspressoModule

    Creamy espresso out of your Flask app
    """
    pass


class ImposterPlugin(object):
    """ImposterPlugin

    I am not really a plugin as I do not inherit from the Plugin class
    """
    pass


class OtherVersionPlugin(Plugin):
    """OtherVersionPlugin

    I am a plugin with a custom version
    """
    version = '2.0'


class MockEntryPoint(EntryPoint):
    def load(self):
        if self.name == 'importfail':
            raise ImportError()
        elif self.name == 'imposter':
            return ImposterPlugin
        elif self.name == 'otherversion':
            return OtherVersionPlugin
        else:
            return EspressoModule




@pytest.fixture
def engine():
    pengine = PluginEngine('test')
    pengine.plugins_to_load = ['espresso']
    return pengine


@pytest.fixture
def mock_entry_point(monkeypatch):
    from pluginengine import engine as engine_mod

    def _mock_entry_points(_, name):
        return {
            'espresso': [MockEntryPoint('espresso', 'test.plugin')],
            'otherversion': [MockEntryPoint('otherversion', 'test.plugin')],
            'someotherstuff': [],
            'doubletrouble': [MockEntryPoint('double', 'double'), MockEntryPoint('double', 'double')],
            'importfail': [MockEntryPoint('importfail', 'test.importfail')],
            'imposter': [MockEntryPoint('imposter', 'test.imposter')]
        }[name]

    def _mock_distribution(name):
        return Distribution(version='1.2.3')

    monkeypatch.setattr(engine_mod, 'iter_entry_points', _mock_entry_points)
    monkeypatch.setattr(engine_mod, 'get_distribution', _mock_distribution)


@pytest.fixture
def loaded_engine(mock_entry_point, engine):
    engine.load_plugins()
    return engine



def test_load(mock_entry_point, engine):
    """
    We can load a plugin
    """

    loaded = {'result': False}

    def _on_load(sender):
        loaded['result'] = True

    plugins_loaded.connect(_on_load)
    engine.load_plugins()

    assert loaded['result'] is True


    assert len(engine.get_failed_plugins()) == 0
    assert list(engine.get_active_plugins()) == ['espresso']

    plugin = engine.get_active_plugins()['espresso']

    assert plugin.title == 'EspressoModule'
    assert plugin.description == 'Creamy espresso out of your Flask app'
    assert plugin.version == '1.2.3'
    assert plugin.package_version == '1.2.3'


def test_custom_version(mock_entry_point, engine):
    engine.plugins_to_load = ['otherversion']
    engine.load_plugins()

    plugin = engine.get_active_plugins()['otherversion']
    assert plugin.package_version == '1.2.3'
    assert plugin.version == '2.0'


def test_fail_non_existing(mock_entry_point, engine):
    """
    Fail if a plugin that is specified in the config does not exist
    """

    engine.plugins_to_load = ['someotherstuff']

    engine.load_plugins()

    assert len(engine.get_failed_plugins()) == 1
    assert len(engine.get_active_plugins()) == 0


def test_fail_noskip(mock_entry_point, engine):
    """
    Fail immediately if no_skip=False
    """

    engine.plugins_to_load = ['someotherstuff']

    assert engine.load_plugins(skip_failed=False) is False


def test_fail_double(mock_entry_point, engine):
    """
    Fail if the same plugin corresponds to two extension points
    """

    engine.plugins_to_load = ['doubletrouble']

    engine.load_plugins()

    assert len(engine.get_failed_plugins()) == 1
    assert len(engine.get_active_plugins()) == 0


def test_fail_import_error(mock_entry_point, engine):
    """
    Fail if impossible to import Plugin
    """

    engine.plugins_to_load = ['importfail']

    engine.load_plugins()

    assert len(engine.get_failed_plugins()) == 1
    assert len(engine.get_active_plugins()) == 0


def test_fail_not_subclass(mock_entry_point, engine):
    """
    Fail if the plugin is not a subclass of `Plugin`
    """

    engine.plugins_to_load = ['imposter']

    engine.load_plugins()

    assert len(engine.get_failed_plugins()) == 1
    assert len(engine.get_active_plugins()) == 0


def test_double_load(loaded_engine):
    """
    Fail if the engine tries to load the plugins a second time
    """

    with raises(RuntimeError) as exc_info:
        loaded_engine.load_plugins()
    assert 'Plugins already loaded' in str(exc_info.value)


def test_has_plugin(loaded_engine):
    """
    Test that has_plugin() returns the correct result
    """
    assert loaded_engine.has_plugin('espresso')
    assert not loaded_engine.has_plugin('someotherstuff')


def test_get_plugin(loaded_engine):
    """
    Test that get_plugin() behaves consistently
    """
    plugin = loaded_engine.get_plugin('espresso')
    assert isinstance(plugin, EspressoModule)
    assert plugin.name == 'espresso'

    assert loaded_engine.get_plugin('someotherstuff') is None


def test_repr(loaded_engine):
    """
    Check that repr(PluginEngine(...)) is OK
    """
    assert repr(loaded_engine) == '<PluginEngine()>'
