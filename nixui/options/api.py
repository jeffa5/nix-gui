import collections
import functools
import json
import os
import subprocess

from nixui.options import parser, nix_eval, object_to_expression
from nixui.utils import tree, store, copy_decorator, cache


NoDefaultSet = ('NO DEFAULT SET',)


#############################
# utility functions / caching
############################
@cache.cache(return_copy=True, retain_hash_fn=cache.configuration_path_hash_fn)
def get_option_data():
    defaults_and_schema = nix_eval.get_all_nixos_options()
    configured_values = {'.'.join(k): v for k, v in parser.get_all_option_values(os.environ['CONFIGURATION_PATH']).items()}
    result = {}
    for option, option_data in defaults_and_schema.items():
        result[option] = dict(option_data)
        if 'default' not in option_data:
            result[option]['default'] = NoDefaultSet
        if option in configured_values:
            result[option]['value_expr'] = configured_values[option]
            try:
                result[option]['value'] = nix_eval.nix_instantiate_eval(configured_values[option])
            except:
                pass
    return result


# TODO: split the above into functions for
# - get option schema
# - get option default
# - get option types


def get_option_values_map():
    # extract actual value
    return {
        option: option_data.get('value', option_data['default'])
        for option, option_data in get_option_data().items()
    }


def get_option_tree():
    options = get_option_data()
    options_tree = tree.Tree()

    for option_name, opt in options.items():
        options_tree.add_leaf(option_name.split('.'), opt)

    return options_tree



@functools.lru_cache(1)
def get_all_packages_map():
    path_name_map = {}
    for package in open('./all_packages_out').readlines():
        pkg_name, pkg_str, store_path = [x.strip() for x in package.split(' ') if x]
        path_name_map[store_path] = pkg_name
    return path_name_map


# TODO: remove
def get_types():
    argumented_types = ['one of', 'integer between', 'string matching the pattern']
    types = collections.Counter()
    for v in get_option_data().values():
        types.update([v['type']])
        continue
        new_types = []
        for t in v['type'].split(' or '):
            for arg_t in argumented_types:
                if arg_t in t:
                    new_types.append(arg_t)
                    break
            else:
                new_types.append(t)
        types.update(new_types)

    return types


################
# get values api
################
def full_option_name(parent_option, sub_option):
    if parent_option and sub_option:
        return '.'.join([parent_option, sub_option])
    elif parent_option:
        return parent_option
    elif sub_option:
        return sub_option
    else:
        return None


def get_next_branching_option(option):
    # 0 children = leaf -> exit
    # more than 1 child = branch -> exit
    branch = [] if option is None else option.split('.')
    node = get_option_tree().get_node(branch)
    while len(node.get_children()) == 1:
        node_type = get_option_type('.'.join(branch))
        if node_type.startswith('attribute set of '):
            break
        key = node.get_children()[0]
        node = node.get_node([key])
        branch += [key]
    return '.'.join(branch)


@functools.lru_cache(1000)
def get_child_options(parent_option):
    # child options sorted by count
    # TODO: sort by hardcoded priority per readme too
    if not parent_option:
        child_options = get_option_tree().get_children([])
    else:
        branch = parent_option.split('.')
        child_options = [f'{parent_option}.{o}' for o in get_option_tree().get_children(branch)]
    return sorted(child_options, key=lambda x: -get_option_count(x))


def get_option_count(parent_option):
    branch = parent_option.split('.') if parent_option else []
    return get_option_tree().get_count(branch)


def get_leaf(option):
    branch = option.split('.') if option else []
    node = get_option_tree().get_node(branch)
    return node.get_leaf()


def get_option_type(option):
    return get_leaf(option).get('type', 'PARENT')


def get_option_description(option):
    return get_leaf(option)['description']


def get_option_value(option):
    # TODO: fix - actual value it isn't always the default
    if 'value' in get_leaf(option):
        return get_leaf(option)['value']
    elif 'default' in get_leaf(option):
        return get_leaf(option)['default']
    else:
        print()
        print('no default or value found for')
        print(option)
        print(get_leaf(option))


###############
# Apply Updates
###############
def apply_updates(option_value_obj_map):
    """
    option_value_obj_map: map between option string and python object form of value
    """
    option_expr_map = {
        tuple(option.split('.')): object_to_expression.get_formatted_expression(value_obj)
        for option, value_obj in option_value_obj_map.items()
    }
    module_string = parser.inject_expressions(
        os.environ['CONFIGURATION_PATH'],  # TODO: fix this hack - we should get the module the option is defined in
        option_expr_map
    )
    # TODO: once stable set save_path to os.environ['CONFIGURATION_PATH']
    if os.environ.get('NIXGUI_CONFIGURATION_PATH_CAN_BE_CORRUPTED'):
        save_path = os.environ['CONFIGURATION_PATH']
    else:
        save_path = os.path.join(
            store.get_store_path(),
            'configurations',
            os.environ['CONFIGURATION_PATH'].strip(r'/'),
        )
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))
    with open(save_path, 'w') as f:
        f.write(module_string)
    return save_path
