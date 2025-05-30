"""
These tests are for the Crystal implementation that uses the Stack meta-environment and
the continuous Lattice Parameters environment. Alternative implementations preceded
this one but have been removed for simplicity. Check commit
9f3477d8e46c4624f9162d755663993b83196546 to see these changes or the history previous
to that commit to consult previous implementations.
"""

import warnings
from collections import Counter

import common
import numpy as np
import pytest
import torch
from torch import Tensor

from gflownet.envs.crystals.crystal import Crystal
from gflownet.envs.crystals.lattice_parameters import TRICLINIC
from gflownet.utils.common import copy, tbool, tfloat

SG_SUBSET_ALL_CLS_PS = [
    1,
    2,
    3,
    6,
    16,
    17,
    67,
    81,
    89,
    127,
    143,
    144,
    146,
    148,
    168,
    169,
    189,
    195,
    200,
    230,
]


@pytest.fixture
def env_mini_comp_first():
    return Crystal(
        composition_kwargs={"elements": 4},
        do_composition_to_sg_constraints=False,
        do_projected_lattice_parameters=False,
        do_sg_before_composition=False,
        space_group_kwargs={"space_groups_subset": list(range(1, 15 + 1)) + [105]},
    )


@pytest.fixture
def env_with_stoichiometry_sg_check():
    return Crystal(
        composition_kwargs={"elements": 4},
        do_projected_lattice_parameters=False,
        do_composition_to_sg_constraints=True,
        do_sg_before_composition=False,
        space_group_kwargs={"space_groups_subset": SG_SUBSET_ALL_CLS_PS},
    )


@pytest.fixture
def env_sg_first():
    return Crystal(
        composition_kwargs={"elements": 4},
        do_projected_lattice_parameters=False,
        do_sg_to_composition_constraints=True,
        do_sg_before_composition=True,
    )


@pytest.fixture
def env_lpsgccg():
    return Crystal(
        composition_kwargs={"elements": 4},
        do_projected_lattice_parameters=True,
        do_sg_to_composition_constraints=True,
        do_sg_before_composition=True,
    )


@pytest.mark.parametrize(
    "env",
    [
        "env_mini_comp_first",
        "env_with_stoichiometry_sg_check",
        "env_sg_first",
    ],
)
def test__environment__initializes_properly(env, request):
    env = request.getfixturevalue(env)
    assert True


@pytest.mark.parametrize(
    "env, idx_composition",
    [
        ("env_mini_comp_first", 0),
        ("env_with_stoichiometry_sg_check", 0),
        ("env_sg_first", 1),
    ],
)
def test__composition_property__returns_expected(env, idx_composition, request):
    env = request.getfixturevalue(env)
    assert env.composition == env.subenvs[idx_composition]


@pytest.mark.parametrize(
    "env, idx_space_group",
    [
        ("env_mini_comp_first", 1),
        ("env_with_stoichiometry_sg_check", 1),
        ("env_sg_first", 0),
    ],
)
def test__space_group_property__returns_expected(env, idx_space_group, request):
    env = request.getfixturevalue(env)
    assert env.space_group == env.subenvs[idx_space_group]


@pytest.mark.parametrize(
    "env, idx_lattice_parameters",
    [
        ("env_mini_comp_first", 2),
        ("env_with_stoichiometry_sg_check", 2),
        ("env_sg_first", 2),
    ],
)
def test__lattice_parameters_property__returns_expected(
    env, idx_lattice_parameters, request
):
    env = request.getfixturevalue(env)
    assert env.lattice_parameters == env.subenvs[idx_lattice_parameters]


@pytest.mark.parametrize(
    "env, source",
    [
        (
            "env_mini_comp_first",
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
        ),
        (
            "env_with_stoichiometry_sg_check",
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
        ),
        (
            "env_sg_first",
            [
                # fmt: off
                0,
                [0, 0, 0],
                {},
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
        ),
    ],
)
def test__source_is_expected(env, source, request):
    env = request.getfixturevalue(env)
    assert env.equal(env.source, source)
    assert env.is_source(source)


@pytest.mark.parametrize(
    "env",
    [
        "env_mini_comp_first",
        "env_with_stoichiometry_sg_check",
        "env_sg_first",
    ],
)
def test__action_space__contains_actions_of_all_subenvs(env, request):
    env = request.getfixturevalue(env)
    action_space = env.action_space
    for stage, subenv in env.subenvs.items():
        assert all(
            [
                env._pad_action(action, stage) in action_space
                for action in subenv.action_space
            ]
        )


@pytest.mark.parametrize(
    "env, states",
    [
        (
            "env_mini_comp_first",
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.12, 0.23, 0.34, 0.45, 0.56, 0.67]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.75, 0.74, 0.73, 0.72, 0.71]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        )
    ],
)
def test__states2policy__is_concatenation_of_subenv_states(env, states, request):
    env = request.getfixturevalue(env)
    # Get policy states from the batch of states converted into each subenv
    states_dict = {stage: [] for stage in env.subenvs}
    for state in states:
        for stage in env.subenvs:
            states_dict[stage].append(env._get_substate(state, stage))
    states_policy_dict = {
        stage: subenv.states2policy(states_dict[stage])
        for stage, subenv in env.subenvs.items()
    }
    states_policy_expected = torch.cat(
        [el for el in states_policy_dict.values()], dim=1
    )
    # Get policy states from env.states2policy
    states_policy = env.states2policy(states)
    assert torch.all(torch.eq(states_policy, states_policy_expected))


@pytest.mark.skip(reason="skip until revised")
@pytest.mark.parametrize(
    "env, states",
    [
        (
            "env_mini_comp_first",
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.12, 0.23, 0.34, 0.45, 0.56, 0.67]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.75, 0.74, 0.73, 0.72, 0.71]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        )
    ],
)
def test__states2proxy__is_concatenation_of_subenv_states(env, states, request):
    env = request.getfixturevalue(env)
    # Get proxy states from the batch of states converted into each subenv
    states_dict = {stage: [] for stage in env.subenvs}
    for state in states:
        for stage in env.subenvs:
            states_dict[stage].append(env._get_substate(state, stage))
    states_proxy_dict = {
        stage: subenv.states2proxy(states_dict[stage])
        for stage, subenv in env.subenvs.items()
    }
    states_proxy_expected = torch.cat([el for el in states_proxy_dict.values()], dim=1)
    # Get proxy states from env.states2proxy
    states_proxy = env.states2proxy(states)
    assert torch.all(torch.eq(states_proxy, states_proxy_expected))


@pytest.mark.parametrize(
    "env, state, states_stages",
    [
        [
            "env_mini_comp_first",
            [0, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_sg_first",
            [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            (
                [0, 0, 0],
                {},
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [1, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [1, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [1, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [-1, -1, -1, -1, -1, -1],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.75, 0.74, 0.73, 0.72, 0.71]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [0.76, 0.75, 0.74, 0.73, 0.72, 0.71],
            ),
        ],
        [
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.75, 0.74, 0.73, 0.72, 0.71]],
            (
                {1: 1, 3: 4},
                [4, 3, 105],
                [0.76, 0.75, 0.74, 0.73, 0.72, 0.71],
            ),
        ],
        [
            "env_sg_first",
            [2, [4, 3, 105], {1: 1, 3: 4}, [0.76, 0.75, 0.74, 0.73, 0.72, 0.71]],
            (
                [4, 3, 105],
                {1: 1, 3: 4},
                [0.76, 0.75, 0.74, 0.73, 0.72, 0.71],
            ),
        ],
    ],
)
def test__get_substate__returns_expected(
    env,
    state,
    states_stages,
    request,
):
    env = request.getfixturevalue(env)
    for stage, state_stage in zip(env.subenvs, states_stages):
        state_subenv = env._get_substate(state, stage)
        assert env.equal(state_subenv, state_stage)


@pytest.mark.parametrize(
    "env, state, dones, has_lattice_parameters, has_composition_constraints, "
    "has_spacegroup_constraints",
    [
        (
            "env_mini_comp_first",
            [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [False, False, False],
            False,
            False,
            False,
        ),
        (
            "env_mini_comp_first",
            [0, {2: 3, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [False, False, False],
            False,
            False,
            False,
        ),
        (
            "env_mini_comp_first",
            [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
            [True, False, False],
            True,
            False,
            False,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [True, True, False],
            True,
            False,
            False,
        ),
        (
            "env_with_stoichiometry_sg_check",
            [2, {1: 4, 3: 4}, [3, 2, 67], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [True, True, False],
            True,
            True,
            False,
        ),
        (
            "env_sg_first",
            [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            [False, False, False],
            False,
            False,
            False,
        ),
        (
            "env_sg_first",
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            [False, False, False],
            False,
            False,
            False,
        ),
        (
            "env_sg_first",
            [1, [4, 3, 105], {1: 3, 2: 1, 4: 6}, [-1, -1, -1, -1, -1, -1]],
            [True, False, False],
            True,
            False,
            True,
        ),
        (
            "env_sg_first",
            [2, [4, 3, 105], {1: 1, 3: 4}, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [True, True, False],
            True,
            False,
            True,
        ),
    ],
)
def test__set_state__sets_state_subenvs_dones_and_constraints(
    env,
    state,
    dones,
    has_lattice_parameters,
    has_composition_constraints,
    has_spacegroup_constraints,
    request,
):
    env = request.getfixturevalue(env)
    env.set_state(state, done=all(dones))
    # Check global state
    assert env.equal(env.state, state)

    # Check states of subenvs
    for stage, subenv in env.subenvs.items():
        assert env.equal(subenv.state, env._get_substate(state, stage))

    # Check dones
    for subenv, done in zip(env.subenvs.values(), dones):
        assert subenv.done == done, state

    # Check lattice parameters
    if has_lattice_parameters:
        assert env.space_group.lattice_system != "None"
        assert env.space_group.lattice_system == env.lattice_parameters.lattice_system

    # Check composition constraints
    if has_composition_constraints:
        n_atoms = env.composition.get_n_atoms_per_element(env.composition.state)
        n_atoms_compatibility_dict = env.subenvs[
            env.stage_spacegroup
        ].build_n_atoms_compatibility_dict(
            n_atoms,
            env.space_group.space_groups.keys(),
        )
        assert n_atoms_compatibility_dict == env.space_group.n_atoms_compatibility_dict

    # Check spacegroup constraints
    if has_spacegroup_constraints:
        assert env.composition.space_group == env.space_group.space_group


@pytest.mark.parametrize(
    "env, state_to_set, state_to_compare, is_source",
    [
        (
            "env_mini_comp_first",
            None,
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [
                # fmt: off
                0,
                {1: 1},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            False,
        ),
        (
            "env_with_stoichiometry_sg_check",
            None,
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_with_stoichiometry_sg_check",
            None,
            [
                # fmt: off
                0,
                {1: 2},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            False,
        ),
        (
            "env_with_stoichiometry_sg_check",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            [
                # fmt: off
                0,
                {},
                [0, 0, 0],
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_sg_first",
            None,
            [
                # fmt: off
                0,
                [0, 0, 0],
                {},
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_sg_first",
            [0, [1, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            [
                # fmt: off
                0,
                [0, 0, 0],
                {},
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            True,
        ),
        (
            "env_sg_first",
            None,
            [
                # fmt: off
                0,
                [1, 0, 0],
                {},
                [-1, -1, -1, -1, -1, -1],
                # fmt: on
            ],
            False,
        ),
    ],
)
def test__is_source_returns_expected(
    env, state_to_set, state_to_compare, is_source, request
):
    env = request.getfixturevalue(env)
    if state_to_set is not None:
        env.set_state(state_to_set)
    assert env.is_source(state_to_compare) == is_source


# @pytest.mark.skip(reason="skip while developping other tests")
@pytest.mark.parametrize(
    "env, state",
    [
        ("env_sg_first", [1, [1, 2, 2], {1: 3, 4: 6}, [-1, -1, -1, -1, -1, -1]]),
        (
            "env_sg_first",
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_sg_first",
            [1, [4, 3, 105], {1: 3, 2: 1, 4: 6}, [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_sg_first",
            [2, [4, 3, 105], {1: 1, 3: 4}, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
        ),
        (
            "env_mini_comp_first",
            [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_mini_comp_first",
            [0, {2: 3, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_mini_comp_first",
            [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
        ),
        (
            "env_with_stoichiometry_sg_check",
            [2, {1: 4, 3: 4}, [3, 2, 67], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
        ),
    ],
)
def test__get_mask_invalid_actions_backward__returns_expected_general_case(
    env, state, request
):
    env = request.getfixturevalue(env)
    env.set_state(state, done=False)
    n_stages = env.n_subenvs
    stage = env._get_stage(state)
    subenv = env.subenvs[stage]
    mask = env.get_mask_invalid_actions_backward()
    mask_subenv = mask[n_stages : n_stages + subenv.mask_dim]
    mask_subenv_expected = subenv.get_mask_invalid_actions_backward(
        env._get_substate(state, stage), done=False
    )
    assert mask_subenv == mask_subenv_expected, state


@pytest.mark.parametrize(
    "env, state",
    [
        ("env_mini_comp_first", [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]]),
        ("env_mini_comp_first", [1, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]]),
        (
            "env_mini_comp_first",
            [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_mini_comp_first",
            [2, {1: 3, 2: 1, 4: 6}, [1, 2, 2], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_mini_comp_first",
            [2, {1: 3, 2: 1, 4: 6}, [2, 1, 3], [-1, -1, -1, -1, -1, -1]],
        ),
        ("env_sg_first", [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]]),
        ("env_sg_first", [1, [1, 2, 2], {}, [-1, -1, -1, -1, -1, -1]]),
        ("env_sg_first", [1, [2, 1, 3], {}, [-1, -1, -1, -1, -1, -1]]),
        ("env_sg_first", [2, [1, 2, 2], {1: 3, 2: 1, 4: 6}, [-1, -1, -1, -1, -1, -1]]),
        ("env_sg_first", [2, [2, 1, 3], {1: 3, 2: 1, 4: 6}, [-1, -1, -1, -1, -1, -1]]),
    ],
)
def test__get_mask_invalid_actions_backward__returns_expected_stage_transition(
    env, state, request
):
    env = request.getfixturevalue(env)
    env.set_state(state, done=False)
    n_stages = env.n_subenvs
    stage = env._get_stage(state)
    if stage == 0:
        assert env.equal(state, env.source)
        return
    stage -= 1
    subenv = env.subenvs[stage]
    mask = env.get_mask_invalid_actions_backward(state, done=False)
    assert mask[stage]
    mask_subenv = mask[n_stages : n_stages + subenv.mask_dim]
    mask_subenv_expected = subenv.get_mask_invalid_actions_backward(
        env._get_substate(state, stage), done=True
    )
    assert mask_subenv == mask_subenv_expected, state


@pytest.mark.parametrize(
    "env, action",
    [
        ("env_mini_comp_first", (0, 1, 1, 0, 0, 0, 0, 0)),
        ("env_mini_comp_first", (0, 3, 4, 0, 0, 0, 0, 0)),
        ("env_sg_first", (0, 2, 105, 0, 0, 0, 0, 0)),
        ("env_sg_first", (0, 1, 1, 0, 0, 0, 0, 0)),
    ],
)
def test__step__action_from_source_changes_state(env, action, request):
    env = request.getfixturevalue(env)
    env.step(action)

    assert env.state != env.source


@pytest.mark.parametrize(
    "env, state_init, action, state_expected",
    [
        (
            "env_with_stoichiometry_sg_check",
            [0, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (0, -1, -1, 0, 0, 0, 0, 0),
            [1, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_with_stoichiometry_sg_check",
            [0, {1: 1, 2: 2}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (0, -1, -1, 0, 0, 0, 0, 0),
            [1, {1: 1, 2: 2}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_with_stoichiometry_sg_check",
            [0, {1: 1, 2: 3, 3: 7}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            (0, -1, -1, 0, 0, 0, 0, 0),
            [1, {1: 1, 2: 3, 3: 7}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
        ),
    ],
)
def test__transitions_from_composition_to_space_group_apply_constraints_correctly(
    env, state_init, action, state_expected, request
):
    env = request.getfixturevalue(env)
    env.set_state(state_init)
    state_next, action_done, valid = env.step(action)

    assert valid
    assert action_done == action
    assert env.equal(env.state, state_next)
    assert env.equal(env.state, state_expected)
    assert env.composition.done

    # Composition -> SG constraints
    n_atoms = env.composition.get_n_atoms_per_element(env.composition.state)
    n_atoms_compatibility_dict = env.space_group.build_n_atoms_compatibility_dict(
        n_atoms,
        env.space_group.space_groups.keys(),
    )
    assert n_atoms_compatibility_dict == env.space_group.n_atoms_compatibility_dict


@pytest.mark.parametrize(
    "env, state_init, action, state_expected",
    [
        (
            "env_sg_first",
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            (0, -1, -1, -1, 0, 0, 0, 0),
            [1, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
        ),
        (
            "env_sg_first",
            [0, [1, 2, 2], {}, [-1, -1, -1, -1, -1, -1]],
            (0, -1, -1, -1, 0, 0, 0, 0),
            [1, [1, 2, 2], {}, [-1, -1, -1, -1, -1, -1]],
        ),
    ],
)
def test__transitions_from_space_group_to_composition_apply_constraints_correctly(
    env, state_init, action, state_expected, request
):
    env = request.getfixturevalue(env)
    env.set_state(state_init)
    state_next, action_done, valid = env.step(action)

    assert valid
    assert action_done == action
    assert env.equal(env.state, state_next)
    assert env.equal(env.state, state_expected)
    assert env.space_group.done

    # SG -> Composition constraints
    assert env.composition.space_group == env.space_group.space_group

    # SG - LP constraints
    assert env.space_group.lattice_system != "None"
    assert env.space_group.lattice_system == env.lattice_parameters.lattice_system


@pytest.mark.parametrize(
    "env, actions, exp_result, last_action_valid",
    [
        (
            "env_mini_comp_first",
            [(0, 1, 1, 0, 0, 0, 0, 0), (0, 3, 4, 0, 0, 0, 0, 0)],
            [0, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
            ],
            [1, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
            ],
            [1, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
            ],
            [1, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            False,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
            ],
            [2, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (2, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1),
            ],
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (2, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1),
                (2, 0.6, 0.5, 0.8, 0.3, 0.2, 0.6, 0),
            ],
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
            False,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.0, 0.44, 0.0, 0.0, 0.0, 0),
            ],
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            True,
        ),
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.66, 0.44, 0.0, 0.0, 0.0, 0),
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
            ],
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            True,
        ),
        (
            "env_sg_first",
            [(0, 2, 105, 0, 0, 0, 0, 0)],
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_sg_first",
            [(0, 2, 105, 0, 0, 0, 0, 0), (0, 2, 105, 0, 0, 0, 0, 0)],
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            False,
        ),
        (
            "env_sg_first",
            [(0, 2, 105, 0, 0, 0, 0, 0), (0, -1, -1, -1, 0, 0, 0, 0)],
            [1, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
            ],
            [1, [4, 3, 105], {3: 4}, [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 1, 2, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, -1, -1, 0, 0, 0, 0, 0),
            ],
            [2, [4, 3, 105], {1: 2, 3: 4}, [-1, -1, -1, -1, -1, -1]],
            True,
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 1, 2, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, -1, -1, 0, 0, 0, 0, 0),
                (2, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1),
                (2, 0.6, 0.5, 0.8, 0.3, 0.2, 0.6, 0),
            ],
            [2, [4, 3, 105], {1: 2, 3: 4}, [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
            False,
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 1, 2, -2, -2, -2, -2, -2),
                (1, 3, 4, -2, -2, -2, -2, -2),
                (1, -1, -1, -2, -2, -2, -2, -2),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.0, 0.44, 0.0, 0.0, 0.0, 0),
            ],
            [2, [4, 3, 105], {1: 2, 3: 4}, [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            True,
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 1, 2, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, -1, -1, 0, 0, 0, 0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.66, 0.44, 0.0, 0.0, 0.0, 0),
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
            ],
            [2, [4, 3, 105], {1: 2, 3: 4}, [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            True,
        ),
    ],
)
def test__step__action_sequence_has_expected_result(
    env, actions, exp_result, last_action_valid, request
):
    env = request.getfixturevalue(env)
    for idx, action in enumerate(actions):
        warnings.filterwarnings("ignore")
        _, _, valid = env.step(action)
        if idx == len(actions) - 1 and not last_action_valid:
            assert not valid
        else:
            assert valid, "Invalid action"

    assert env.equal(env.state, exp_result)
    assert valid == last_action_valid


@pytest.mark.parametrize(
    "env, state_init, state_end, actions, last_action_valid",
    [
        (
            "env_mini_comp_first",
            [0, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [(0, 3, 4, 0, 0, 0, 0, 0), (0, 1, 1, 0, 0, 0, 0, 0)],
            True,
        ),
        (
            "env_mini_comp_first",
            [1, {1: 1, 3: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [1, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (1, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [-1, -1, -1, -1, -1, -1]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (1, -1, -1, -1, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (2, 0.66, 0.0, 0.44, 0.0, 0.0, 0.0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_mini_comp_first",
            [2, {1: 1, 3: 4}, [4, 3, 105], [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            [
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
                (2, 0.66, 0.0, 0.44, 0.0, 0.0, 0.0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, 1, 1, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_sg_first",
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_sg_first",
            [1, [4, 3, 105], {1: 1, 3: 4}, [-1, -1, -1, -1, -1, -1]],
            [0, [4, 3, 105], {}, [-1, -1, -1, -1, -1, -1]],
            [
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, 1, 1, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_sg_first",
            [2, [4, 3, 105], {1: 1, 3: 4}, [-1, -1, -1, -1, -1, -1]],
            [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            [
                (1, -1, -1, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, 1, 1, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (0, 2, 105, 0, 0, 0, 0, 0),
            ],
            True,
        ),
        (
            "env_sg_first",
            [2, [4, 3, 105], {1: 1, 3: 4}, [0.76, 0.76, 0.74, 0.4, 0.4, 0.4]],
            [0, [0, 0, 0], {}, [-1, -1, -1, -1, -1, -1]],
            [
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
                (2, 0.66, 0.0, 0.44, 0.0, 0.0, 0.0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (1, -1, -1, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, 1, 1, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (0, 2, 105, 0, 0, 0, 0, 0),
            ],
            True,
        ),
    ],
)
def test__step_backwards__action_sequence_has_expected_result(
    env,
    state_init,
    state_end,
    actions,
    last_action_valid,
    request,
):
    env = request.getfixturevalue(env)

    # Hacky way to also test if first action global EOS
    if actions[0] == env.eos:
        env.set_state(state_init, done=True)
    else:
        env.set_state(state_init, done=False)
    assert env.equal(env.state, state_init)
    for action in actions:
        warnings.filterwarnings("ignore")
        _, _, valid = env.step_backwards(action)

    assert env.equal(env.state, state_end)
    assert valid == last_action_valid


@pytest.mark.parametrize(
    "env, actions",
    [
        (
            "env_mini_comp_first",
            [
                (0, 1, 1, 0, 0, 0, 0, 0),
                (0, 3, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 2, 105, 0, 0, 0, 0, 0),
                (1, -1, -1, -1, 0, 0, 0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.66, 0.44, 0.0, 0.0, 0.0, 0),
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
            ],
        ),
        (
            "env_sg_first",
            [
                (0, 2, 105, 0, 0, 0, 0, 0),
                (0, -1, -1, -1, 0, 0, 0, 0),
                (1, 1, 2, 0, 0, 0, 0, 0),
                (1, 3, 4, 0, 0, 0, 0, 0),
                (1, -1, -1, 0, 0, 0, 0, 0),
                (2, 0.1, 0.1, 0.3, 0.0, 0.0, 0.0, 1),
                (2, 0.66, 0.66, 0.44, 0.0, 0.0, 0.0, 0),
                (2, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf),
            ],
        ),
    ],
)
def test__reset__sets_source_and_triclinic(env, actions, request):
    env = request.getfixturevalue(env)
    for action in actions:
        env.step(action)

    assert env.state != env.source
    for subenv in env.subenvs.values():
        assert subenv.state != subenv.source
    assert env.lattice_parameters.lattice_system != TRICLINIC

    env.reset()

    assert env.equal(env.state, env.source)
    for subenv in env.subenvs.values():
        assert env.equal(subenv.state, subenv.source)
    assert env.lattice_parameters.lattice_system == TRICLINIC


def test__get_policy_outputs__is_the_concatenation_of_subenvs(env_mini_comp_first):
    env = env_mini_comp_first
    policy_output_composition = env.composition.get_policy_output(
        env.composition.fixed_distr_params
    )
    policy_output_space_group = env.space_group.get_policy_output(
        env.space_group.fixed_distr_params
    )
    policy_output_lattice_parameters = env.subenvs[
        env.stage_latticeparameters
    ].get_policy_output(env.lattice_parameters.fixed_distr_params)
    policy_output_cat = torch.cat(
        (
            policy_output_composition,
            policy_output_space_group,
            policy_output_lattice_parameters,
        )
    )
    policy_output = env.get_policy_output(env.fixed_distr_params)
    assert torch.all(torch.eq(policy_output_cat, policy_output))


def test___get_policy_outputs_of_subenv__returns_correct_output(env_mini_comp_first):
    env = env_mini_comp_first
    n_states = 5
    policy_output_composition = torch.tile(
        env.composition.get_policy_output(env.composition.fixed_distr_params),
        dims=(n_states, 1),
    )
    policy_output_space_group = torch.tile(
        env.space_group.get_policy_output(env.space_group.fixed_distr_params),
        dims=(n_states, 1),
    )
    policy_output_lattice_parameters = torch.tile(
        env.lattice_parameters.get_policy_output(
            env.lattice_parameters.fixed_distr_params
        ),
        dims=(n_states, 1),
    )
    policy_outputs = torch.tile(
        env.get_policy_output(env.fixed_distr_params), dims=(n_states, 1)
    )
    assert torch.all(
        torch.eq(
            env._get_policy_outputs_of_subenv(policy_outputs, env.stage_composition),
            policy_output_composition,
        )
    )
    assert torch.all(
        torch.eq(
            env._get_policy_outputs_of_subenv(policy_outputs, env.stage_spacegroup),
            policy_output_space_group,
        )
    )
    assert torch.all(
        torch.eq(
            env._get_policy_outputs_of_subenv(
                policy_outputs, env.stage_latticeparameters
            ),
            policy_output_lattice_parameters,
        )
    )


@pytest.mark.repeat(10)
@pytest.mark.parametrize(
    "env",
    [
        "env_mini_comp_first",
        "env_with_stoichiometry_sg_check",
        "env_sg_first",
    ],
)
def test__step_random__does_not_crash_from_source(env, request):
    env = request.getfixturevalue(env)
    env.reset()
    env.step_random()
    assert True


@pytest.mark.repeat(10)
@pytest.mark.parametrize(
    "env, states",
    [
        (
            "env_mini_comp_first",
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_mini_comp_first",
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_mini_comp_first",
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.5, 0.5, 0.3, 0.4, 0.4, 0.4]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.45, 0.45, 0.33, 0.4, 0.4, 0.4]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_sg_first",
            [
                [1, [8, 4, 210], {}, [-1, -1, -1, -1, -1, -1]],
                [1, [8, 4, 210], {1: 8}, [-1, -1, -1, -1, -1, -1]],
                [1, [7, 1, 169], {1: 6}, [-1, -1, -1, -1, -1, -1]],
            ],
        ),
    ],
)
def test__sample_actions_forward__returns_valid_actions(env, states, request):
    env = request.getfixturevalue(env)
    n_states = len(states)
    # Get masks
    # Important: we need to set the state of the environment before computing
    # the mask because otherwise the environment can have wrong attributes,
    # such as self.space_group
    masks = []
    for state in states:
        env.reset()
        env.set_state(state, done=False)
        masks.append(env.get_mask_invalid_actions_forward())
    masks = tbool(masks, device=env.device)
    # Build policy outputs
    params = env.random_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Sample actions
    actions, _ = env.sample_actions_batch(
        policy_outputs, masks, states, is_backward=False
    )
    # Sample actions are valid
    for state, action in zip(states, actions):
        if env._get_stage(state) == env.stage_latticeparameters:
            continue
        env.set_state(state, done=False)
        assert action in env.get_valid_actions(backward=False)


@pytest.mark.repeat(10)
@pytest.mark.parametrize(
    "env, states",
    [
        (
            "env_mini_comp_first",
            [
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_mini_comp_first",
            [
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_mini_comp_first",
            [
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_mini_comp_first",
            [
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.5, 0.5, 0.3, 0.4, 0.4, 0.4]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.45, 0.45, 0.33, 0.4, 0.4, 0.4]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
        ),
        (
            "env_sg_first",
            [
                [1, [8, 4, 210], {}, [-1, -1, -1, -1, -1, -1]],
                [1, [8, 4, 210], {1: 8}, [-1, -1, -1, -1, -1, -1]],
                [1, [7, 1, 169], {1: 6}, [-1, -1, -1, -1, -1, -1]],
            ],
        ),
    ],
)
def test__sample_actions_backward__returns_valid_actions(env, states, request):
    env = request.getfixturevalue(env)
    n_states = len(states)
    # Get masks
    # Important: we need to set the state of the environment before computing
    # the mask because otherwise the environment can have wrong attributes,
    # such as self.space_group
    masks = []
    for state in states:
        env.set_state(state, done=False)
        masks.append(env.get_mask_invalid_actions_backward())
    masks = tbool(masks, device=env.device)
    # Build policy outputs
    params = env.random_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Sample actions
    actions, _ = env.sample_actions_batch(
        policy_outputs, masks, states, is_backward=True
    )
    # Sample actions are valid
    for state, action in zip(states, actions):
        if env._get_stage(state) == env.stage_latticeparameters:
            continue
        env.set_state(state, done=False)
        assert action in env.get_valid_actions(backward=True)


@pytest.mark.parametrize(
    "states, actions",
    [
        [
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, 1, 7, 0, 0, 0, 0, 0),
                (0, 3, 16, 0, 0, 0, 0, 0),
                (0, 1, 6, 0, 0, 0, 0, 0),
                (0, 3, 8, 0, 0, 0, 0, 0),
                (0, 2, 11, 0, 0, 0, 0, 0),
                (0, 3, 9, 0, 0, 0, 0, 0),
            ],
        ],
        [
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, 1, 6, 0, 0, 0, 0, 0),
                (1, 2, 14, 0, 0, 0, 0, 0),
                (1, 2, 2, 1, 0, 0, 0, 0),
                (1, 2, 1, 3, 0, 0, 0, 0),
            ],
        ],
        [
            [
                [0, {}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.5, 0.5, 0.3, 0.4, 0.4, 0.4]],
                [2, {1: 1, 3: 4}, [4, 3, 105], [0.45, 0.45, 0.33, 0.4, 0.4, 0.4]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, 1, 15, 0, 0, 0, 0, 0),
                (0, 1, 2, 0, 0, 0, 0, 0),
                (1, 2, 7, 0, 0, 0, 0, 0),
                (2, 0.49, 0.40, 0.40, 0.37, 0.35, 0.36, 0.0),
                (1, 2, 1, 1, 0, 0, 0, 0),
                (1, 2, 1, 3, 0, 0, 0, 0),
                (0, 2, 11, 0, 0, 0, 0, 0),
                (0, 3, 9, 0, 0, 0, 0, 0),
                (1, 2, 2, 3, 0, 0, 0, 0),
                (0, 3, 2, 0, 0, 0, 0, 0),
                (2, 0.27, 0.28, 0.30, 0.39, 0.37, 0.29, 0.0),
                (2, 0.32, 0.30, 0.45, 0.33, 0.42, 0.39, 0.0),
                (0, 4, 4, 0, 0, 0, 0, 0),
            ],
        ],
    ],
)
def test__get_logprobs_forward__returns_valid_actions(
    env_mini_comp_first, states, actions
):
    env = env_mini_comp_first
    n_states = len(states)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    # Important: we need to set the state of the environment before computing
    # the mask because otherwise the environment can have wrong attributes,
    # such as self.space_group
    masks = []
    for state in states:
        env.set_state(state, done=False)
        masks.append(env.get_mask_invalid_actions_forward())
    masks = tbool(masks, device=env.device)
    # Build policy outputs
    params = env.random_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states, is_backward=False
    )
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.parametrize(
    "states, actions",
    [
        [
            [
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, 2, 4, 0, 0, 0, 0, 0),
                (0, 2, 4, 0, 0, 0, 0, 0),
                (0, 1, 3, 0, 0, 0, 0, 0),
                (0, 1, 3, 0, 0, 0, 0, 0),
                (0, 4, 6, 0, 0, 0, 0, 0),
            ],
        ],
        [
            [
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, -1, -1, 0, 0, 0, 0, 0),
                (1, 0, 1, 0, 0, 0, 0, 0),
                (1, 1, 1, 1, 0, 0, 0, 0),
            ],
        ],
        [
            [
                [0, {2: 4}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                # [2, {1: 1, 3: 4}, [4, 3, 105], [0.1, 0.1, 0.3, 0.4, 0.4, 0.4]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 1, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                [1, {1: 3, 2: 1, 4: 6}, [1, 2, 0], [-1, -1, -1, -1, -1, -1]],
                [0, {1: 3, 2: 1, 4: 6}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
                # [2, {1: 1, 3: 4}, [4, 3, 105], [0.5, 0.5, 0.3, 0.4, 0.4, 0.4]],
                # [2, {1: 1, 3: 4}, [4, 3, 105], [0.45, 0.45, 0.33, 0.4, 0.4, 0.4]],
                [0, {2: 4, 3: 3}, [0, 0, 0], [-1, -1, -1, -1, -1, -1]],
            ],
            [
                (0, 2, 4, 0, 0, 0, 0, 0),
                (0, -1, -1, 0, 0, 0, 0, 0),
                # (2, 0.10, 0.10, 0.17, 0.0, 0.0, 0.0, 0.0),
                (1, 0, 1, 0, 0, 0, 0, 0),
                (1, 1, 1, 1, 0, 0, 0, 0),
                (0, 1, 3, 0, 0, 0, 0, 0),
                (0, 1, 3, 0, 0, 0, 0, 0),
                (1, 1, 2, 1, 0, 0, 0, 0),
                (0, 2, 1, 0, 0, 0, 0, 0),
                # (2, 0.37, 0.37, 0.23, 0.0, 0.0, 0.0, 0.0),
                # (2, 0.23, 0.23, 0.11, 0.0, 0.0, 0.0, 0.0),
                (0, 3, 3, 0, 0, 0, 0, 0),
            ],
        ],
    ],
)
def test__get_logprobs_backward__returns_valid_actions(
    env_mini_comp_first, states, actions
):
    env = env_mini_comp_first
    n_states = len(states)
    actions = tfloat(actions, float_type=env.float, device=env.device)
    # Get masks
    # Important: we need to set the state of the environment before computing
    # the mask because otherwise the environment can have wrong attributes,
    # such as self.space_group
    masks = []
    for state in states:
        env.set_state(state, done=False)
        masks.append(env.get_mask_invalid_actions_backward())
    masks = tbool(masks, device=env.device)
    # Build policy outputs
    params = env.random_distr_params
    policy_outputs = torch.tile(env.get_policy_output(params), dims=(n_states, 1))
    # Get log probs
    logprobs = env.get_logprobs(
        policy_outputs, actions, masks, states, is_backward=True
    )
    assert torch.all(torch.isfinite(logprobs))


@pytest.mark.repeat(10)
@pytest.mark.parametrize(
    "env",
    [
        "env_mini_comp_first",
        "env_with_stoichiometry_sg_check",
        "env_sg_first",
    ],
)
def test__trajectory_random__does_not_crash_from_source(env, request):
    env = request.getfixturevalue(env)
    env.reset()
    env.trajectory_random()
    assert True


class TestMiniCrystalCompFirst(common.BaseTestsContinuous):
    """Common tests for a mini crystal stack with composition first environment."""

    @pytest.fixture(autouse=True)
    def setup(self, env_mini_comp_first):
        self.env = env_mini_comp_first
        self.repeats = {
            "test__reset__state_is_source": 10,
            "test__forward_actions_have_nonzero_backward_prob": 10,
            "test__backward_actions_have_nonzero_forward_prob": 10,
            "test__trajectories_are_reversible": 10,
            "test__step_random__does_not_sample_invalid_actions_forward": 10,
            "test__step_random__does_not_sample_invalid_actions_backward": 10,
            "test__get_mask__is_consistent_regardless_of_inputs": 10,
            "test__get_valid_actions__is_consistent_regardless_of_inputs": 10,
            "test__sample_actions__get_logprobs__return_valid_actions_and_logprobs": 10,
            "test__get_parents_step_get_mask__are_compatible": 10,
            "test__sample_backwards_reaches_source": 10,
            "test__state2readable__is_reversible": 20,
            "test__gflownet_minimal_runs": 3,
        }
        self.n_states = {
            "test__backward_actions_have_nonzero_forward_prob": 3,
            "test__sample_backwards_reaches_source": 3,
            "test__get_logprobs__all_finite_in_random_forward_transitions": 10,
            "test__get_logprobs__all_finite_in_random_backward_transitions": 10,
        }
        self.batch_size = {
            "test__sample_actions__get_logprobs__batched_forward_trajectories": 10,
            "test__sample_actions__get_logprobs__batched_backward_trajectories": 10,
            "test__get_logprobs__all_finite_in_accumulated_forward_trajectories": 10,
            "test__gflownet_minimal_runs": 10,
        }


class TestCrystalSGFirst(common.BaseTestsContinuous):
    """Common tests for crystal stack with space group first."""

    @pytest.fixture(autouse=True)
    def setup(self, env_sg_first):
        self.env = env_sg_first
        self.repeats = {
            "test__reset__state_is_source": 10,
            "test__forward_actions_have_nonzero_backward_prob": 10,
            "test__backward_actions_have_nonzero_forward_prob": 10,
            "test__trajectories_are_reversible": 10,
            "test__step_random__does_not_sample_invalid_actions_forward": 10,
            "test__step_random__does_not_sample_invalid_actions_backward": 10,
            "test__get_mask__is_consistent_regardless_of_inputs": 10,
            "test__get_valid_actions__is_consistent_regardless_of_inputs": 10,
            "test__sample_actions__get_logprobs__return_valid_actions_and_logprobs": 10,
            "test__get_parents_step_get_mask__are_compatible": 10,
            "test__sample_backwards_reaches_source": 10,
            "test__state2readable__is_reversible": 20,
            "test__gflownet_minimal_runs": 3,
        }
        self.n_states = {
            "test__backward_actions_have_nonzero_forward_prob": 3,
            "test__sample_backwards_reaches_source": 3,
            "test__get_logprobs__all_finite_in_random_forward_transitions": 10,
            "test__get_logprobs__all_finite_in_random_backward_transitions": 10,
        }
        self.batch_size = {
            "test__sample_actions__get_logprobs__batched_forward_trajectories": 10,
            "test__sample_actions__get_logprobs__batched_backward_trajectories": 10,
            "test__get_logprobs__all_finite_in_accumulated_forward_trajectories": 10,
            "test__gflownet_minimal_runs": 10,
        }


class TestCrystalLPSGCCG(common.BaseTestsContinuous):
    """Common tests for crystal stack with SGCCG lattice parameters."""

    @pytest.fixture(autouse=True)
    def setup(self, env_lpsgccg):
        self.env = env_lpsgccg
        self.repeats = {
            "test__reset__state_is_source": 10,
            "test__forward_actions_have_nonzero_backward_prob": 10,
            "test__backward_actions_have_nonzero_forward_prob": 10,
            "test__trajectories_are_reversible": 10,
            "test__step_random__does_not_sample_invalid_actions_forward": 10,
            "test__step_random__does_not_sample_invalid_actions_backward": 10,
            "test__get_mask__is_consistent_regardless_of_inputs": 10,
            "test__get_valid_actions__is_consistent_regardless_of_inputs": 10,
            "test__sample_actions__get_logprobs__return_valid_actions_and_logprobs": 10,
            "test__get_parents_step_get_mask__are_compatible": 10,
            "test__sample_backwards_reaches_source": 10,
            "test__state2readable__is_reversible": 20,
            "test__gflownet_minimal_runs": 3,
        }
        self.n_states = {
            "test__backward_actions_have_nonzero_forward_prob": 3,
            "test__sample_backwards_reaches_source": 3,
            "test__get_logprobs__all_finite_in_random_forward_transitions": 10,
            "test__get_logprobs__all_finite_in_random_backward_transitions": 10,
        }
        self.batch_size = {
            "test__sample_actions__get_logprobs__batched_forward_trajectories": 10,
            "test__sample_actions__get_logprobs__batched_backward_trajectories": 10,
            "test__get_logprobs__all_finite_in_accumulated_forward_trajectories": 10,
            "test__gflownet_minimal_runs": 10,
        }
