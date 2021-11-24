import os

from nixui.options import api, types
from nixui.options.option_tree import OptionTree
from nixui.options.attribute import Attribute
from nixui.options.option_definition import OptionDefinition

import pytest


SAMPLES_PATH = 'tests/sample'


def test_option_tree_simple():
    attr = Attribute(['foo', 'bar'])
    t = OptionTree(
        {attr: {'_type': 'mytype'}},
        {attr: OptionDefinition.from_object('myvalue')},
    )
    assert t.get_type(attr) == 'mytype'
    assert t.get_definition(attr).obj == 'myvalue'


def test_option_tree_simple_attr_set():
    attr = Attribute(['foo', 'bar'])
    t = OptionTree(
        {attr: {'_type': types.AttrsOfType(types.StrType())}},
        {},
    )
    child_attr = Attribute(['foo', 'bar', 'baz'])
    t.set_definition(child_attr, OptionDefinition.from_object('val'))
    assert t.get_type(child_attr) == types.StrType()
    assert t.get_definition(child_attr).obj == 'val'


@pytest.mark.datafiles(SAMPLES_PATH)
def test_set_configuration_loads():
    option_tree = api.get_option_tree(
        os.path.abspath(os.path.join(SAMPLES_PATH, 'set_configuration.nix'))
    )
    for attr, old_d, new_d in option_tree.iter_changes(get_configured_changes=True):
        # evaluate expression strings
        (attr, old_d.expression_string, new_d.expression_string)


@pytest.mark.datafiles(SAMPLES_PATH)
def test_list_children_simple():
    option_tree = api.get_option_tree(
        os.path.abspath(os.path.join(SAMPLES_PATH, 'configuration.nix'))
    )
    children = option_tree.children(
        Attribute('networking.firewall.allowedTCPPorts')
    )
    assert [c.configured_definition.obj for c in children.values()] == [80, 443]
