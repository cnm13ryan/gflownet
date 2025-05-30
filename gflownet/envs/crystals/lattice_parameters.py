"""
Classes to represent continuous lattice parameters environments.

An implementation for discrete lattice parameters preceded this one but has been
removed for simplicity. Check commit 9f3477d8e46c4624f9162d755663993b83196546 to see
these changes or the history previous to that commit to consult previous
implementations.
"""

from typing import List, Optional, Tuple, Union

import numpy
import torch
from scipy.linalg import expm, logm
from torch import Tensor
from torchtyping import TensorType

from gflownet.envs.cube import ContinuousCube
from gflownet.utils.common import copy, tfloat
from gflownet.utils.crystals.constants import (
    CUBIC,
    HEXAGONAL,
    MONOCLINIC,
    ORTHORHOMBIC,
    RHOMBOHEDRAL,
    TETRAGONAL,
    TRICLINIC,
)

LENGTH_PARAMETER_NAMES = ("a", "b", "c")
ANGLE_PARAMETER_NAMES = ("alpha", "beta", "gamma")
PARAMETER_NAMES = LENGTH_PARAMETER_NAMES + ANGLE_PARAMETER_NAMES


# Matrices used in the LatticeParametersSGCCG environment
B1 = numpy.array([[0, 1, 0], [1, 0, 0], [0, 0, 0]])
B2 = numpy.array([[0, 0, 1], [0, 0, 0], [1, 0, 0]])
B3 = numpy.array([[0, 0, 0], [0, 0, 1], [0, 1, 0]])
B4 = numpy.array([[1, 0, 0], [0, -1, 0], [0, 0, 0]])
B5 = numpy.array([[1, 0, 0], [0, 1, 0], [0, 0, -2]])
B6 = numpy.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])


# TODO: figure out a way to inherit the (discrete) LatticeParameters env or create a
# common class for both discrete and continous with the common methods.
class LatticeParameters(ContinuousCube):
    """
    Continuous lattice parameters environment for crystal structures generation.

    Models lattice parameters (three edge lengths and three angles describing unit
    cell) with the constraints given by the provided lattice system (see
    https://en.wikipedia.org/wiki/Bravais_lattice). This is implemented by inheriting
    from the (continuous) cube environment, creating a mapping between cell position
    and edge length or angle, and imposing lattice system constraints on their values.

    The environment is a hyper cube of dimensionality 6 (the number of lattice
    parameters), but it takes advantage of the mask of ignored dimensions implemented
    in the Cube environment.

    The values of the state will remain in the default [0, 1] range of the Cube, but
    they are mapped to [min_length, max_length] in the case of the lengths and
    [min_angle, max_angle] in the case of the angles.
    """

    def __init__(
        self,
        lattice_system: str,
        min_length: Optional[float] = 1.0,
        max_length: Optional[float] = 350.0,
        min_angle: Optional[float] = 50.0,
        max_angle: Optional[float] = 150.0,
        **kwargs,
    ):
        """
        Args
        ----
        lattice_system : str
            One of the seven lattice systems. By default, the triclinic lattice system
            is used, which has no constraints.

        min_length : float
            Minimum value of the lengths.

        max_length : float
            Maximum value of the lengths.

        min_angle : float
            Minimum value of the angles.

        max_angle : float
            Maximum value of the angles.
        """
        self.continuous = True
        self.lattice_system = lattice_system
        self.min_length = min_length
        self.max_length = max_length
        self.length_range = self.max_length - self.min_length
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.angle_range = self.max_angle - self.min_angle
        super().__init__(n_dim=6, **kwargs)
        # Setup constraints after the call of super to avoid getting the variable
        # self.ignored_dims overriden by the Cube initialization
        self._setup_constraints()

    # TODO: if source, keep as is
    def _statevalue2length(self, value):
        return self.min_length + value * self.length_range

    def _length2statevalue(self, length):
        return (length - self.min_length) / self.length_range

    # TODO: if source, keep as is
    def _statevalue2angle(self, value):
        return self.min_angle + value * self.angle_range

    def _angle2statevalue(self, angle):
        return (angle - self.min_angle) / self.angle_range

    def _get_param(self, state, param):
        if hasattr(self, param):
            return getattr(self, param)
        else:
            if param in LENGTH_PARAMETER_NAMES:
                return self._statevalue2length(state[self._get_index_of_param(param)])
            elif param in ANGLE_PARAMETER_NAMES:
                return self._statevalue2angle(state[self._get_index_of_param(param)])
            else:
                raise ValueError(f"{param} is not a valid lattice parameter")

    def _set_param(self, state, param, value):
        param_idx = self._get_index_of_param(param)
        if param_idx is not None:
            if param in LENGTH_PARAMETER_NAMES:
                state[param_idx] = self._length2statevalue(value)
            elif param in ANGLE_PARAMETER_NAMES:
                state[param_idx] = self._angle2statevalue(value)
            else:
                raise ValueError(f"{param} is not a valid lattice parameter")
        return state

    def _get_index_of_param(self, param):
        param_idx = f"{param}_idx"
        if hasattr(self, param_idx):
            return getattr(self, param_idx)
        else:
            return None

    def set_lattice_system(self, lattice_system: str):
        """
        Sets the lattice system of the unit cell and updates the constraints.
        """
        self.lattice_system = lattice_system
        self._setup_constraints()

    def _setup_constraints(self):
        """
        Computes the mask of ignored dimensions, given the constraints imposed by the
        lattice system. Sets self.ignored_dims.
        """
        # Lengths: a, b, c
        # a == b == c
        if self.lattice_system in [CUBIC, RHOMBOHEDRAL]:
            lengths_ignored_dims = [False, True, True]
            self.a_idx = 0
            self.b_idx = 0
            self.c_idx = 0
        # a == b != c
        elif self.lattice_system in [HEXAGONAL, TETRAGONAL]:
            lengths_ignored_dims = [False, True, False]
            self.a_idx = 0
            self.b_idx = 0
            self.c_idx = 2
        # a != b and a != c and b != c
        elif self.lattice_system in [MONOCLINIC, ORTHORHOMBIC, TRICLINIC]:
            lengths_ignored_dims = [False, False, False]
            self.a_idx = 0
            self.b_idx = 1
            self.c_idx = 2
        else:
            raise ValueError(f"{self.lattice_system} is not a valid lattice system")
        # Angles: alpha, beta, gamma
        # alpha == beta == gamma == 90.0
        if self.lattice_system in [CUBIC, ORTHORHOMBIC, TETRAGONAL]:
            angles_ignored_dims = [True, True, True]
            self.alpha_idx = None
            self.alpha = 90.0
            self.alpha_state = self._angle2statevalue(self.alpha)
            self.beta_idx = None
            self.beta = 90.0
            self.beta_state = self._angle2statevalue(self.beta)
            self.gamma_idx = None
            self.gamma = 90.0
            self.gamma_state = self._angle2statevalue(self.gamma)
        #  alpha == beta == 90.0 and gamma == 120.0
        elif self.lattice_system == HEXAGONAL:
            angles_ignored_dims = [True, True, True]
            self.alpha_idx = None
            self.alpha = 90.0
            self.alpha_state = self._angle2statevalue(self.alpha)
            self.beta_idx = None
            self.beta = 90.0
            self.beta_state = self._angle2statevalue(self.beta)
            self.gamma_idx = None
            self.gamma = 120.0
            self.gamma_state = self._angle2statevalue(self.gamma)
        # alpha == gamma == 90.0 and beta != 90.0
        elif self.lattice_system == MONOCLINIC:
            angles_ignored_dims = [True, False, True]
            self.alpha_idx = None
            self.alpha = 90.0
            self.alpha_state = self._angle2statevalue(self.alpha)
            self.beta_idx = 4
            self.gamma_idx = None
            self.gamma = 90.0
            self.gamma_state = self._angle2statevalue(self.gamma)
        # alpha == beta == gamma != 90.0
        elif self.lattice_system == RHOMBOHEDRAL:
            angles_ignored_dims = [False, True, True]
            self.alpha_idx = 3
            self.beta_idx = 3
            self.gamma_idx = 3
        # alpha != beta, alpha != gamma, beta != gamma
        elif self.lattice_system == TRICLINIC:
            angles_ignored_dims = [False, False, False]
            self.alpha_idx = 3
            self.beta_idx = 4
            self.gamma_idx = 5
        else:
            raise NotImplementedError
        self.ignored_dims = lengths_ignored_dims + angles_ignored_dims

    def _step(
        self,
        action: Tuple[float],
        backward: bool,
    ) -> Tuple[List[float], Tuple[float], bool]:
        """
        Updates the dimensions of the state corresponding to the ignored dimensions
        after a call to the Cube's _step().
        """
        state, action, valid = super()._step(action, backward)
        for idx, (param, is_ignored) in enumerate(
            zip(PARAMETER_NAMES, self.ignored_dims)
        ):
            if not is_ignored:
                continue
            param_idx = self._get_index_of_param(param)
            if param_idx is not None:
                state[idx] = state[param_idx]
            else:
                state[idx] = getattr(self, f"{param}_state")
        self.state = copy(state)
        return self.state, action, valid

    def _unpack_lengths_angles(
        self, state: Optional[List[float]] = None
    ) -> Tuple[Tuple, Tuple]:
        """
        Helper that 1) unpacks values coding lengths and angles from the state or from
        the attributes of the instance and 2) converts them to actual edge lengths and
        angles in the target units (angstroms or degrees).
        """
        state = self._get_state(state)

        a, b, c, alpha, beta, gamma = [
            self._get_param(state, p) for p in PARAMETER_NAMES
        ]
        return (a, b, c), (alpha, beta, gamma)

    def parameters2state(
        self, parameters: Tuple = None, lengths: Tuple = None, angles: Tuple = None
    ) -> List[float]:
        """Converts a set of lattice parameters in angstroms and degrees into an
        environment state, with the parameters in the [0, 1] range.

        The parameters may be passed as a single tuple parameters containing the six
        parameters or via separate lengths and angles. If parameters is not None,
        lengths and angles are ignored.

        Parameters
        ----------
        parameters : tuple (optional)
            The six lattice parameters (a, b, c, alpha, beta, gamma) in target units
            (angstroms and degrees).
        lengths : tuple (optional)
            A triplet of length lattice parameters (a, b, c) in angstroms. Ignored if
            parameters is not None.
        angles : tuple (optional)
            A triplet of angle lattice parameters (alpha, beta, gamma) in degrees.
            Ignored if parameters is not None.

        Returns
        -------
        state
            A state in environment format.
        """
        if parameters is None:
            if lengths is None or angles is None:
                raise ValueError("Cannot determine all six parameters.")
            parameters = lengths + angles

        state = copy(self.source)
        for param, value in zip(PARAMETER_NAMES, parameters):
            state = self._set_param(state, param, value)
        return state

    def states2proxy(
        self, states: Union[List, TensorType["batch", "state_dim"]]
    ) -> TensorType["height", "width", "batch"]:
        """
        Prepares a batch of states in "environment format" for a proxy: states are
        mapped from [0; 1] to edge lengths and angles using min_length, max_length,
        min_angle and max_angle, via _statevalue2length() and _statevalue2angle().

        Args
        ----
        states : list or tensor
            A batch of states in environment format, either as a list of states or as a
            single tensor.

        Returns
        -------
        A tensor containing all the states in the batch.
        """
        states = tfloat(states, device=self.device, float_type=self.float)
        return torch.cat(
            [
                self._statevalue2length(states[:, :3]),
                self._statevalue2angle(states[:, 3:]),
            ],
            dim=1,
        )

    def state2readable(self, state: Optional[List[float]] = None) -> str:
        """
        Converts the state into a human-readable string in the format "(a, b, c),
        (alpha, beta, gamma)".
        """
        state = self._get_state(state)

        lengths, angles = self._unpack_lengths_angles(state)
        return f"{lengths}, {angles}"

    def readable2state(self, readable: str) -> List[float]:
        """
        Converts a human-readable representation of a state into the standard format.
        """
        for c in ["(", ")", " "]:
            readable = readable.replace(c, "")
        values = readable.split(",")
        values = [float(value) for value in values]

        return self.parameters2state(values)

    def is_valid(self, state: List) -> bool:
        """
        Determines whether a state is valid, according to the attributes of the
        environment.

        Parameters
        ----------
        state : list
            A state in environment format. If None, then lengths and angles will be
            used instead.

        Returns
        -------
        bool
            True if the state is valid according to the attributes of the environment;
            False otherwise.
        """
        lengths, angles = self._unpack_lengths_angles(state)
        # Check lengths
        if any([l < self.min_length or l > self.max_length for l in lengths]):
            return False
        if any([l < self.min_angle or l > self.max_angle for l in angles]):
            return False

        # If all checks are passed, return True
        return True


class LatticeParametersSGCCG(ContinuousCube):
    """
    Continuous lattice parameters environment for crystal structures generation.

    Models lattice parameters (three edge lengths and three angles describing unit
    cell) with the constraints given by the provided lattice system (see
    https://en.wikipedia.org/wiki/Bravais_lattice). This is implemented by inheriting
    from the (continuous) cube environment, creating a mapping between cell position
    and edge length or angle, and imposing lattice system constraints on their values.

    The environment is implemented using a hyper cube of dimensionality 6, and it takes
    advantage of the mask of ignored dimensions implemented in the Cube environment.

    This version of the LatticeParameters environment implements the projection method
    outlined in the SPACE GROUP CONSTRAINED CRYSTAL GENERATION
    (https://arxiv.org/pdf/2402.03992) article. This projection method ensures that the
    lattice parameters remain valid throughout a trajectory in this environment. As a
    consequence of this method, this environment implements three different
    spaces/representations for lattice parameters :
    state space <--> projection space <--> lattice parameter space.

    State space : the state space representation corresponds to the continuous hyper
    cube state representation of the parent class. This is a 6D continuous space
    (although some dimensions might be ignored using the mask of ignored dimensions
    implemented in the Cube environment) where each value is in the default [0, 1] range
    of the cube class.

    Projection space : this is a 6D continuous space used to represent symmetric 3x3
    matrices. Each dimension has its own min and max value defined by the environment.
    Any point in this space can be converted to a symmetric 3x3 matrix by
    using its coordinates as coefficients for a weighted sum of the matrices B1, B2,
    B3, B4, B5, and B6. These six matrices form an orthogonal basis for the space of
    symmetric 3x3 matrices.
    The mapping between the state space and the projection space is dimension-wise
    linear. Each dimension in the state space has a linear relationship with the
    corresponding dimension in this projection space.

    Lattice parameter space : this is a 6D continuous space representing the parameters
    of a crystal lattice : three lengths (a, b, c) and three angles (alpha, beta, gamma).
    Lengths must be higher than 0 and angles must be between 0 and 180 degrees. However,
    not all possible points in this space correspond to valid lattice parameters. When
    taken together, the 6 lattice parameters must describe a unit cell of strictly
    positive non-imaginary volume.
    The mapping between the projection space and the lattice parameter space is
    complicated and non-linear. It relies on obtain a symmetric 3x3 matrix from the
    corresponding to the point in projection space and then taking the exponential
    mapping of that matrix to obtain a matrix from which the lattice parameters can
    be extracted (see equations 23 and 24 in the paper's A3 appendix).
    """

    def __init__(
        self,
        lattice_system: str,
        **kwargs,
    ):
        """
        Args
        ----
        lattice_system : str
            One of the seven lattice systems. By default, the triclinic lattice system
            is used, which has no constraints.
        """
        self.continuous = True
        self.lattice_system = lattice_system

        # TODO : Find better values for these variables? We might make the values of
        # these variables dependant on some input parameters to the environment like
        # min/max angle/lengths. However, the relationship between the projection
        # space and the space of lattice parameters involves a matrix exponential so
        # this might be non-trivial to do in practice.
        # These default values were found through empirical testing. They seem to
        # correspond to bounds in which the numerical stability of the environment is
        # good enough (with more extreme values, the mapping between projection and
        # lattice params might break down). These bounds are also sufficient vast to
        # represent with angles between 10 and 170 degrees and side lengths between
        # 1 and 1000 Angstroms
        self.min_projection_values = [-3 / 2, -3 / 2, -3 / 2, -9 / 2, -3, -3 / 2]
        self.max_projection_values = [3 / 2, 3 / 2, 3 / 2, 9 / 2, 3, 7]

        super().__init__(n_dim=6, **kwargs)
        # Setup constraints after the call of super to avoid getting the variable
        # self.ignored_dims overriden by the Cube initialization
        self._setup_constraints()

    def _state2projection(self, state=None):
        """
        Transforms a state into its equivalent representation in the projection space

        Parameters
        ----------
        state : list
            A state in environment format. If None, then the current state will be used
            instead

        Returns
        -------
        proj : list
            Projection space representation equivalent to the provided state
            representation.
        """
        state = self._get_state(state)
        proj = [
            min_proj_v + s * (max_proj_v - min_proj_v)
            for s, min_proj_v, max_proj_v in zip(
                state, self.min_projection_values, self.max_projection_values
            )
        ]
        return proj

    def _projection2state(self, projection):
        """
        Transforms a representation in the projection space into its equivalent
        representation in the state space

        Parameters
        ----------
        projection : list
            A representation in projection space.

        Returns
        -------
        state : list
            Environment state equivalent to the provided representation in projection
            space.
        """
        state = [
            (proj - min_proj_v) / (max_proj_v - min_proj_v)
            for proj, min_proj_v, max_proj_v in zip(
                projection, self.min_projection_values, self.max_projection_values
            )
        ]
        return state

    def _projection2lattice(self, projection):
        """
        Transforms a representation in the projection space into its equivalent
        representation in the space of lattice parameters

        Parameters
        ----------
        projection : list
            A representation in projection space.

        Returns
        -------
        list
            Lattice parameters (a, b, c, alpha, beta, gamma) corresponding to the input
            representation in the projection space
        """
        # Convert the vector of the projection state to the symmetric matrix s
        # (see Eq. 24 in the paper)
        k1, k2, k3, k4, k5, k6 = projection
        s = k1 * B1 + k2 * B2 + k3 * B3 + k4 * B4 + k5 * B5 + k6 * B6

        # Compute the matrix J (see Eqs. 23 and 24 in the paper)
        j = expm(2 * s)

        # Extract the values of the lattice parameters from matrix J (see Eq. 23 in the
        # paper)
        a = j[0, 0] ** 0.5
        b = j[1, 1] ** 0.5
        c = j[2, 2] ** 0.5
        alpha = numpy.rad2deg(numpy.arccos(j[1, 2] / (b * c)))
        beta = numpy.rad2deg(numpy.arccos(j[0, 2] / (a * c)))
        gamma = numpy.rad2deg(numpy.arccos(j[0, 1] / (a * b)))

        return [a, b, c, alpha, beta, gamma]

    def _lattice2projection(self, lattice_params):
        """
        Transforms a set of lattice parameters into its equivalent representation in
        the projection space.

        Parameters
        ----------
        lattice_params : list
            A set of lattice parameter. In order : a, b, c, alpha, beta, gamma.

        Returns
        -------
        list
            Representation in projection space equivalent to the input lattice
            parameters.
        """
        # Extract the values of the individual lattice params
        a, b, c, alpha, beta, gamma = lattice_params

        # Compute the matrix J from the values of the lattice parameters
        # (see Eq. 23 in the paper)
        ab_cos_gamma = a * b * numpy.cos(numpy.deg2rad(gamma))
        ac_cos_beta = a * c * numpy.cos(numpy.deg2rad(beta))
        bc_cos_alpha = b * c * numpy.cos(numpy.deg2rad(alpha))

        j = numpy.array(
            [
                [a**2, ab_cos_gamma, ac_cos_beta],
                [ab_cos_gamma, b**2, bc_cos_alpha],
                [ac_cos_beta, bc_cos_alpha, c**2],
            ]
        )

        # Compute the matrix S from the matrix J (see Eqs. 23 and 24 in the paper)
        s, error = logm(j, disp=False)
        if error > 1e-9:
            raise ValueError(f"logm error {error} larger than 1e-9")
        s /= 2

        # Recover the projection coefficients from the matrix S
        # (see Eq. 24 in the paper)
        k1 = s[0, 1]
        k2 = s[0, 2]
        k3 = s[1, 2]
        k6 = (s[0, 0] + s[1, 1] + s[2, 2]) / 3
        k5 = (s[0, 0] + s[1, 1]) / 2 - k6
        k4 = s[0, 0] - (k5 + k6)
        return [k1, k2, k3, k4, k5, k6]

    def state2lattice(self, state=None):
        """
        Transforms a state into its equivalent lattice parameters

        Parameters
        ----------
        state : list
            A state in environment format. If None, then the current state will be used
            instead

        Returns
        -------
        proj : list
            Lattice parameters equivalent to the provided state representation. In
            format [[a, b, c], [alpha, beta, gamma]] for compatibility with previous
            lattice parameter environment.
        """
        # Obtain the vector of projection coefficients satistying the env constraints
        state = self._get_state(state)
        projection_vector = self._state2projection(state)
        projection_vector = self.apply_projection_constraints(projection_vector)

        lattice_params = self._projection2lattice(projection_vector)
        a, b, c, alpha, beta, gamma = self.apply_lattice_constraints(lattice_params)
        return [[a, b, c], [alpha, beta, gamma]]

    def apply_projection_constraints(self, projection_vector):
        """
        Apply the environment constraints to a state representation in projection space.

        Args
        ----
        projection_vector : list
            State representation in projection space

        Returns
        -------
        constrained_projection_vector : list
            State representation in projection space, compatible with the environment
            constraints.
        """
        # Alter the vector of projection coefficients to enforce the env constraints
        constrained_projection_vector = []
        for i in range(len(self.projection_tied_values)):
            # If the env enforces a specific value for this element, apply it
            if self.projection_fixed_values[i] is not None:
                proj_ele_value = self.projection_fixed_values[i]

            # If the env forces this element to be equal to another element, overwrite
            # its value with the value of the other element
            elif self.projection_tied_values[i] is not None:
                tied_idx = self.projection_tied_values[i]
                proj_ele_value = constrained_projection_vector[tied_idx]

            # If there is no constraint, keep the value of this vector element as-is
            else:
                proj_ele_value = projection_vector[i]

            constrained_projection_vector.append(proj_ele_value)

        return constrained_projection_vector

    def apply_lattice_constraints(self, lattice_params):
        """
        Apply the environment constraints to a set of lattice parameters.

        Args
        ----
        lattice_params : list
            Lattice parameters, in order (a, b, c, alpha, beta, gamma).

        Returns
        -------
        constrained_lattice_params : list
            Lattice parameters in the same order as in the input, modified if needed to
            be compatible with the environment constraints.
        """
        # Alter the lattice parameters to enforce the env constraints
        constrained_lattice_params = []
        for i in range(len(self.lattice_params_tied_values)):
            # If the env enforces a specific value for this lattice param, apply it
            if self.lattice_params_fixed_values[i] is not None:
                param_value = self.lattice_params_fixed_values[i]

            # If the env forces this lattice parameter to be equal to another parameter,
            # overwrite its value with the value of the other lattice parameter
            elif self.lattice_params_tied_values[i] is not None:
                tied_idx = self.lattice_params_tied_values[i]
                param_value = constrained_lattice_params[tied_idx]

            # If there is no constraint, keep the value of this lattice parameter as-is
            else:
                param_value = lattice_params[i]

            constrained_lattice_params.append(param_value)

        return constrained_lattice_params

    def set_lattice_system(self, lattice_system: str):
        """
        Sets the lattice system of the unit cell and updates the constraints.

        Args
        ----
        lattice_system : str
            Name of the lattice system for which to produce lattice parameters.
        """
        self.lattice_system = lattice_system
        self._setup_constraints()

    def _setup_constraints(self):
        """
        Sets up environment constraints based on the environment lattice system. This
        involves setting up the ignored dimensions as well as the dimensions, in
        projection and lattice parameters space, which may have fixed values or values
        tied to other dimensions.

        This method sets the following attributes :
        - self.ignored_dims
            This attribute describes which dimension of the parent hypercube state space
            might be ignored. A dimension is ignored when it isn't required, such as
            when a particular dimension of the hypercube should have a fixed value or
            when this dimension should have its value tied to another dimension.
        - self.projection_tied_values
            This attributes describes, in projection space, which dimensions should have
            their value tied to the value of another dimension. This attribute is a list
            of 6 values, one per projection space dimension. Each value is either None,
            if the dimension isn't tied to another dimension, or an int representing the
            index of another dimension to which this dimension should be identical.
        - self.projection_fixed_values
            This attributes describes, in projection space, which dimensions should be
            fixed at a certain value, independant of the agent's action. This attribute
            is a list of 6 values, one per projection space dimension. Each value is
            either None, if the value of that dimension isn't fixed, or a float/integer
            value indicating the value that this dimension should take.
        - self.lattice_params_tied_values
            This attributes describes, in lattice parameter space, which parameters
            should have their value tied to the value of another parameter. This
            attribute is a list of 6 values, one per lattice parameter. The order is
            (a, b, c, alpha, beta, gamma). Each value is either None, if the lattice
            parameter isn't tied to another parameter, or an int representing the
            index of another parameter to which this parameter should be identical.
        - self.lattice_params_fixed_values
            This attributes describes, in lattice parameter space, which parameters
            should be fixed at a certain value, independant of the agent's action.
            This attribute is a list of 6 values, one per lattice parameter. The order
            is (a, b, c, alpha, beta, gamma). Each value is either None, if the value of
            that lattice parameter isn't fixed, or a float/integer value indicating the
            value that this lattice parameter should take.
        """

        if self.lattice_system == TRICLINIC:
            # No constraints
            self.ignored_dims = [False] * 6
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [None] * 6
            self.lattice_params_tied_values = [None] * 6
            self.lattice_params_fixed_values = [None] * 6

        elif self.lattice_system == MONOCLINIC:
            # Constraint : alpha == gamma == 90 degrees
            self.ignored_dims = [True, False, True, False, False, False]
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [0, None, 0, None, None, None]
            self.lattice_params_tied_values = [None] * 6
            self.lattice_params_fixed_values = [None, None, None, 90, None, 90]

        elif self.lattice_system == ORTHORHOMBIC:
            # Constraint : alpha == beta == gamma == 90 degrees
            self.ignored_dims = [True, True, True, False, False, False]
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [0, 0, 0, None, None, None]
            self.lattice_params_tied_values = [None] * 6
            self.lattice_params_fixed_values = [None, None, None, 90, 90, 90]

        elif self.lattice_system == TETRAGONAL:
            # Constraints :
            # - alpha == beta == gamma == 90 degrees
            # - a == b
            self.ignored_dims = [True, True, True, True, False, False]
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [0, 0, 0, 0, None, None]
            self.lattice_params_tied_values = [None, 0, None, None, None, None]
            self.lattice_params_fixed_values = [None, None, None, 90, 90, 90]

        elif self.lattice_system == HEXAGONAL:
            # Constraints :
            # - alpha == beta == 90 degrees
            # - gamma == 120 degrees
            # - a == b
            self.ignored_dims = [True, True, True, True, False, False]
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [-numpy.log(3) / 4, 0, 0, 0, None, None]
            self.lattice_params_tied_values = [None, 0, None, None, None, None]
            self.lattice_params_fixed_values = [None, None, None, 90, 90, 120]

        elif self.lattice_system == RHOMBOHEDRAL:
            # Constraints :
            # alpha == beta == gamma != 90 degrees
            # a == b == c
            self.ignored_dims = [False, True, True, True, True, False]
            self.projection_tied_values = [None, 0, 0, None, None, None]
            self.projection_fixed_values = [None, None, None, 0, 0, None]
            self.lattice_params_tied_values = [None, 0, 0, None, 3, 3]
            self.lattice_params_fixed_values = [None] * 6

        elif self.lattice_system == CUBIC:
            # Constraints :
            # - alpha == beta == gamma == 90 degrees
            # - a == b == c
            self.ignored_dims = [True, True, True, True, True, False]
            self.projection_tied_values = [None] * 6
            self.projection_fixed_values = [0, 0, 0, 0, 0, None]
            self.lattice_params_tied_values = [None, 0, 0, None, None, None]
            self.lattice_params_fixed_values = [None, None, None, 90, 90, 90]

        else:
            raise ValueError(f"{self.lattice_system} is not a valid lattice system")

    def _step(
        self,
        action: Tuple[float],
        backward: bool,
    ) -> Tuple[List[float], Tuple[float], bool]:
        """
        Updates self.state given a non-EOS action. This method is called by both step()
        and step_backwards(), with the corresponding value of argument backward.

        Args
        ----
        action : tuple
            Action to be executed. An action is a tuple of length n_dim, with the
            absolute increment for each dimension.

        backward : bool
            If True, perform backward step. Otherwise (default), perform forward step.

        Returns
        -------
        self.state : list
            The environment state after executing the action

        action : int
            Action executed

        valid : bool
            False, if the action is not allowed for the current state, e.g. stop at the
            root state

        """
        # Apply action to the state
        state, action, valid = super()._step(action, backward)

        # Ensure that the new state satisfies the constraints
        projection_vector = self._state2projection(state)
        projection_vector = self.apply_projection_constraints(projection_vector)
        state = self._projection2state(projection_vector)

        # Update the state and return the appropriate values
        self.state = copy(state)
        return self.state, action, valid

    def parameters2state(
        self, parameters: Tuple = None, lengths: Tuple = None, angles: Tuple = None
    ) -> List[float]:
        """Converts a set of lattice parameters in angstroms and degrees into an
        environment state, with the parameters in the [0, 1] range.

        The parameters may be passed as a single tuple parameters containing the six
        parameters or via separate lengths and angles. If parameters is not None,
        lengths and angles are ignored.

        Parameters
        ----------
        parameters : tuple (optional)
            The six lattice parameters (a, b, c, alpha, beta, gamma) in target units
            (angstroms and degrees).
        lengths : tuple (optional)
            A triplet of length lattice parameters (a, b, c) in angstroms. Ignored if
            parameters is not None.
        angles : tuple (optional)
            A triplet of angle lattice parameters (alpha, beta, gamma) in degrees.
            Ignored if parameters is not None.

        Returns
        -------
        state
            A state in environment format.
        """
        if parameters is None:
            if lengths is None or angles is None:
                raise ValueError("Cannot determine all six parameters.")
            parameters = lengths + angles

        projection_vector = self._lattice2projection(parameters)
        state = self._projection2state(projection_vector)
        return state

    def states2proxy(
        self, states: Union[List, TensorType["batch", "state_dim"]]
    ) -> TensorType["height", "width", "batch"]:
        """
        Prepares a batch of states in "environment format" for a proxy: states are
        mapped from [0; 1] to edge lengths and angles.

        Args
        ----
        states : list or tensor
            A batch of states in environment format, either as a list of states or as a
            single tensor.

        Returns
        -------
        A tensor containing all the states in the batch.
        """
        states = tfloat(states, device=self.device, float_type=self.float)
        proxy_input = [self.state2lattice(s.numpy()) for s in states]
        return tfloat(proxy_input, device=self.device, float_type=self.float).flatten(1)

    def state2readable(self, state: Optional[List[float]] = None) -> str:
        """
        Converts the state into a human-readable string in the format "(a, b, c),
        (alpha, beta, gamma)".
        """
        state = self._get_state(state)
        (a, b, c), (alpha, beta, gamma) = self.state2lattice(state)
        return f"({a}, {b}, {c}), ({alpha}, {beta}, {gamma})"

    def readable2state(self, readable: str) -> List[float]:
        """
        Converts a human-readable representation of a state into the state format.
        """
        for c in ["(", ")", " "]:
            readable = readable.replace(c, "")
        values = readable.split(",")
        values = [float(value) for value in values]

        projection_vector = self._lattice2projection(*values)
        state = self._projection2state(projection_vector)

        return state

    def is_valid(self, state: List) -> bool:
        """
        Determines whether a state is valid, according to the attributes of the
        environment.

        Parameters
        ----------
        state : list
            A state in environment format. If None, then the current state will be used
            instead

        Returns
        -------
        bool
            True if the state is valid according to the attributes of the environment;
            False otherwise.
        """
        state = self._get_state(state)
        projection_vector = self._state2projection(state)
        for p, min_p, max_p in zip(
            projection_vector, self.min_projection_values, self.max_projection_values
        ):
            if p < min_p or p > max_p:
                return False
        return True
