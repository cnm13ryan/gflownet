import os
import random
from copy import deepcopy
from functools import partial
from os.path import expandvars
from pathlib import Path
from typing import List, Union

import numpy as np
import torch
from hydra import compose, initialize_config_dir
from hydra.utils import get_original_cwd, instantiate
from omegaconf import DictConfig, OmegaConf
from torchtyping import TensorType

from gflownet.utils.policy import parse_policy_config


def set_device(device: Union[str, torch.device]):
    """
    Get `torch` device from device.

    Examples
    --------
    >>> set_device("cuda")
    device(type='cuda')

    >>> set_device("cpu")
    device(type='cpu')

    >>> set_device(torch.device("cuda"))
    device(type='cuda')

    Parameters
    ----------
    device : Union[str, torch.device]
        Device.

    Returns
    -------
    torch.device
        `torch` device.
    """
    if isinstance(device, torch.device):
        return device
    if device.lower() == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    else:
        return torch.device("cpu")


def set_float_precision(precision: Union[int, torch.dtype]):
    """
    Get `torch` float type from precision.

    Examples
    --------
    >>> set_float_precision(32)
    torch.float32

    >>> set_float_precision(torch.float32)
    torch.float32

    Parameters
    ----------
    precision : Union[int, torch.dtype]
        Precision.

    Returns
    -------
    torch.dtype
        `torch` float type.

    Raises
    ------
    ValueError
        If precision is not one of [16, 32, 64].
    """
    if isinstance(precision, torch.dtype):
        return precision
    if precision == 16:
        return torch.float16
    elif precision == 32:
        return torch.float32
    elif precision == 64:
        return torch.float64
    else:
        raise ValueError("Precision must be one of [16, 32, 64]")


def set_int_precision(precision: Union[int, torch.dtype]):
    """
    Get `torch` integer type from `int` precision.

    Examples
    --------
    >>> set_int_precision(32)
    torch.int32

    >>> set_int_precision(torch.int32)
    torch.int32

    Parameters
    ----------
    precision : Union[int, torch.dtype]
        Integer precision.

    Returns
    -------
    torch.dtype
        `torch` integer type.

    Raises
    ------
    ValueError
        If precision is not one of [16, 32, 64].
    """
    if isinstance(precision, torch.dtype):
        return precision
    if precision == 16:
        return torch.int16
    elif precision == 32:
        return torch.int32
    elif precision == 64:
        return torch.int64
    else:
        raise ValueError("Precision must be one of [16, 32, 64]")


def torch2np(x):
    """
    Convert a torch tensor to a numpy array.

    Parameters
    ----------
    x : Union[torch.Tensor, np.ndarray, list]
        Data to be converted.

    Returns
    -------
    np.ndarray
        Converted data.
    """
    if hasattr(x, "is_cuda") and x.is_cuda:
        x = x.detach().cpu()
    return np.array(x)


def download_file_if_not_exists(path: str, url: str):
    """
    Download a file from google drive if path doestn't exist.
    url should be in the format: https://drive.google.com/uc?id=FILE_ID
    """
    import gdown

    path = Path(path)
    if not path.is_absolute():
        # to avoid storing downloaded files with the logs, prefix is set to the original working dir
        prefix = get_original_cwd()
        path = Path(prefix) / path
    if not path.exists():
        path.absolute().parent.mkdir(parents=True, exist_ok=True)
        gdown.download(url, str(path.absolute()), quiet=False)
    return path


def resolve_path(path: str) -> Path:
    """
    Resolve a path by expanding environment variables, user home directory, and making
    it absolute.

    Examples
    --------
    >>> resolve_path("~/scratch/$SLURM_JOB_ID/data")
    Path("/home/user/scratch/12345/data")

    Parameters
    ----------
    path : Union[str, Path]
        Path to be resolved.

    Returns
    -------
    Path
        Resolved path.
    """
    return Path(expandvars(str(path))).expanduser().resolve()


def find_latest_checkpoint(ckpt_dir):
    """
    Find the latest checkpoint in the input directory.

    If the directory contains a checkpoint file with the name "final", that checkpoint
    is returned. Otherwise, the latest checkpoint is returned based on the iteration
    number set in the file names.

    Parameters
    ----------
    ckpt_dir : Union[str, Path]
        Directory in which to search for the checkpoints.

    Returns
    -------
    Path
        Path to the latest checkpoint.

    Raises
    ------
    ValueError
        If no checkpoint files are found in the input directory.
    """
    ckpt_dir = Path(ckpt_dir)
    final = [f for f in ckpt_dir.glob(f"*final*")]
    if len(final) > 0:
        return final[0]
    ckpts = [f for f in ckpt_dir.glob(f"iter_*")]
    if not ckpts:
        raise ValueError(
            f"No checkpoints found in {ckpt_dir} with pattern iter_* or *final*"
        )
    return sorted(ckpts, key=lambda f: float(f.stem.split("iter_")[1]))[-1]


def read_hydra_config(rundir=None, config_name="config"):
    if rundir is None:
        rundir = Path(config_name)
        hydra_dir = rundir.parent
        config_name = rundir.name
    else:
        hydra_dir = rundir / ".hydra"

    with initialize_config_dir(
        version_base=None, config_dir=str(hydra_dir), job_name="xxx"
    ):
        return compose(config_name=config_name)


def gflownet_from_config(config, env=None):
    """
    Create GFlowNet from a Hydra OmegaConf config.

    Parameters
    ----------
    config : DictConfig
        Config.

    env : GFlowNetEnv
        Optional environment instance to be used in the initialization.

    Returns
    -------
    GFN
        GFlowNet.
    """
    # Logger
    logger = instantiate(config.logger, config, _recursive_=False)

    # The proxy is required by the GFlowNetAgent for computing rewards
    proxy = instantiate(
        config.proxy,
        device=config.device,
        float_precision=config.float_precision,
    )

    # Using Hydra's partial instantiation, see:
    # https://hydra.cc/docs/advanced/instantiate_objects/overview/#partial-instantiation
    # If env is passed as an argument, we create an env maker with a partial
    # instantiation from the copy method of the environment (this is used in unit
    # tests, for example). Otherwise, we create the env maker with partial
    # instantiation from the config.
    if env is not None:
        env_maker = partial(env.copy)
    else:
        env_maker = instantiate(
            config.env,
            device=config.device,
            float_precision=config.float_precision,
            _partial_=True,
        )
        env = env_maker()

    # TOREVISE: set up proxy so when buffer calls it (when it creates train / test
    # dataset) it has the correct infro from env
    # proxy.setup(env)
    buffer = instantiate(
        config.buffer,
        env=env,
        proxy=proxy,
        datadir=logger.datadir,
    )

    # The evaluator is used to compute metrics and plots
    evaluator = instantiate(config.evaluator)

    # The policy is used to model the probability of a forward/backward action
    forward_config = parse_policy_config(config, kind="forward")
    backward_config = parse_policy_config(config, kind="backward")

    forward_policy = instantiate(
        forward_config,
        env=env,
        device=config.device,
        float_precision=config.float_precision,
    )
    backward_policy = instantiate(
        backward_config,
        env=env,
        device=config.device,
        float_precision=config.float_precision,
        base=forward_policy,
    )

    # State flow
    if config.gflownet.state_flow is not None:
        state_flow = instantiate(
            config.gflownet.state_flow,
            env=env,
            device=config.device,
            float_precision=config.float_precision,
            base=forward_policy,
        )
    else:
        state_flow = None

    # GFlowNet Agent
    gflownet = instantiate(
        config.gflownet,
        device=config.device,
        float_precision=config.float_precision,
        env_maker=env_maker,
        proxy=proxy,
        forward_policy=forward_policy,
        backward_policy=backward_policy,
        state_flow=state_flow,
        buffer=buffer,
        logger=logger,
        evaluator=evaluator,
    )

    return gflownet


def load_gflownet_from_rundir(
    rundir,
    no_wandb=True,
    print_config=False,
    device=None,
    load_last_checkpoint=True,
    is_resumed: bool = False,
):
    """
    Load GFlowNet from a run path (directory with a `.hydra` directory inside).

    Parameters
    ----------
    rundir : Union[str, Path]
        Path to the run directory. Must contain a `.hydra` directory.
    no_wandb : bool, optional
        Whether to disable wandb in the GFN init, by default True.
    print_config : bool, optional
        Whether to print the loaded config, by default False.
    device : str, optional
        Device to which the models should be moved. If None (default), take the device
        from the loaded config.
    load_last_checkpoint : bool, optional
        Whether to load the final models, by default True.
    is_resumed : bool, optional
        Whether the GFlowNet is loaded to resume training.

    Returns
    -------
    Tuple[GFN, DictConfig]
        Loaded GFlowNet and the loaded config.

    Raises
    ------
    ValueError
        If no checkpoints are found in the directory.
    """
    rundir = resolve_path(rundir)

    # Read experiment config
    config = OmegaConf.load(Path(rundir) / ".hydra" / "config.yaml")
    # Resolve variables
    config = OmegaConf.to_container(config, resolve=True)
    # Re-create OmegaCong DictConfig
    config = OmegaConf.create(config)

    if print_config:
        print(OmegaConf.to_yaml(config))

    # Device
    if device is None:
        device = config.device

    if no_wandb:
        # Disable wandb
        config.logger.do.online = False

    # -----------------------------------------
    # -----  Load last model checkpoints  -----
    # -----------------------------------------

    if load_last_checkpoint:
        checkpoint_latest = find_latest_checkpoint(rundir / config.logger.logdir.ckpts)
        checkpoint = torch.load(checkpoint_latest, map_location=set_device(device))

        # Set run id in logger to enable WandB resume
        config.logger.run_id = checkpoint["run_id"]

        # Set up Buffer configuration to load data sets and buffers from run
        if checkpoint["buffer"]["train"]:
            config.buffer.train = {
                "type": "pkl",
                "path": checkpoint["buffer"]["train"],
            }
        if checkpoint["buffer"]["test"]:
            config.buffer.test = {
                "type": "pkl",
                "path": checkpoint["buffer"]["test"],
            }
        if checkpoint["buffer"]["replay"]:
            config.buffer.replay_buffer = checkpoint["buffer"]["replay"]
        # load them here

        if is_resumed:
            config.logger.logdir.root = rundir
            config.logger.is_resumed = True

    # Initialize a GFlowNet agent from the configuration
    gflownet = gflownet_from_config(config)

    # Load checkpoint into the GFlowNet agent
    if load_last_checkpoint:
        gflownet.load_checkpoint(checkpoint)

    return gflownet, config


def batch_with_rest(start, stop, step, tensor=False):
    """
    Yields batches of indices from start to stop with step size. The last batch may be
    smaller than step.

    Parameters
    ----------
    start : int
        Start index
    stop : int
        End index (exclusive)
    step : int
        Step size
    tensor : bool, optional
        Whether to return a `torch` tensor of indices instead of a `numpy` array, by
        default False.

    Yields
    ------
    Union[np.ndarray, torch.Tensor]
        Batch of indices
    """
    for i in range(start, stop, step):
        if tensor:
            yield torch.arange(i, min(i + step, stop))
        else:
            yield np.arange(i, min(i + step, stop))


def tfloat(x, device, float_type):
    """
    Convert input to a float tensor. If the input is a list of tensors, the tensors
    are stacked along the first dimension.

    The resulting tensor is moved to the specified device.

    Parameters
    ----------
    x : Union[List[torch.Tensor], torch.Tensor, List[Union[int, float]], Union[int,
    float]]
        Input to be converted to a float tensor.
    device : torch.device
        Device to which the tensor should be moved.
    float_type : torch.dtype
        Float type to which the tensor should be converted.

    Returns
    -------
    Union[torch.Tensor, List[torch.Tensor]]
        Float tensor.
    """
    if isinstance(x, list) and torch.is_tensor(x[0]):
        return torch.stack(x).to(device=device, dtype=float_type)
    if torch.is_tensor(x):
        return x.to(device=device, dtype=float_type)
    else:
        return torch.tensor(x, dtype=float_type, device=device)


def tlong(x, device):
    """
    Convert input to a long tensor. If the input is a list of tensors, the tensors
    are stacked along the first dimension.

    The resulting tensor is moved to the specified device.

    Parameters
    ----------
    x : Union[List[torch.Tensor], torch.Tensor, List[Union[int, float]], Union[int,
    float]]
        Input to be converted to a long tensor.
    device : torch.device
        Device to which the tensor should be moved.

    Returns
    -------
    Union[torch.Tensor, List[torch.Tensor]]
        Long tensor.
    """
    if isinstance(x, list) and torch.is_tensor(x[0]):
        return torch.stack(x).to(device=device, dtype=torch.long)
    if torch.is_tensor(x):
        return x.to(device=device, dtype=torch.long)
    else:
        return torch.tensor(x, dtype=torch.long, device=device)


def tint(x, device, int_type):
    """
    Convert input to an integer tensor. If the input is a list of tensors, the tensors
    are stacked along the first dimension.

    The resulting tensor is moved to the specified device.

    Parameters
    ----------
    x : Union[List[torch.Tensor], torch.Tensor, List[Union[int, float]], Union[int,
    float]]
        Input to be converted to an integer tensor.
    device : torch.device
        Device to which the tensor should be moved.
    int_type : torch.dtype
        Integer type to which the tensor should be converted.

    Returns
    -------
    Union[torch.Tensor, List[torch.Tensor]]
        Integer tensor.
    """
    if isinstance(x, list) and torch.is_tensor(x[0]):
        return torch.stack(x).to(device=device, dtype=int_type)
    if torch.is_tensor(x):
        return x.to(device=device, dtype=int_type)
    else:
        return torch.tensor(x, dtype=int_type, device=device)


def tbool(x, device):
    """
    Convert input to a boolean tensor. If the input is a list of tensors, the tensors
    are stacked along the first dimension.

    The resulting tensor is moved to the specified device.

    Parameters
    ----------
    x : Union[List[torch.Tensor], torch.Tensor, List[Union[int, float]], Union[int,
    float]]
        Input to be converted to a boolean tensor.
    device : torch.device
        Device to which the tensor should be moved.

    Returns
    -------
    Union[torch.Tensor, List[torch.Tensor]]
        Boolean tensor.
    """
    if isinstance(x, list) and torch.is_tensor(x[0]):
        return torch.stack(x).to(device=device, dtype=torch.bool)
    if torch.is_tensor(x):
        return x.to(device=device, dtype=torch.bool)
    else:
        return torch.tensor(x, dtype=torch.bool, device=device)


def concat_items(list_of_items, indices=None):
    """
    Concatenates a list of items into a single tensor or array.

    Parameters
    ----------
    list_of_items :
        List of items to be concatenated, i.e. list of arrays or list of tensors.
    indices : Union[List[np.ndarray], List[torch.Tensor]], optional
        Indices to select in the resulting concatenated tensor or array, by default
        None.

    Returns
    -------
    Union[np.ndarray, torch.Tensor]
        Concatenated tensor or array, with optional selection of indices.

    Raises
    ------
    NotImplementedError
        If the input type is not supported, i.e., not a list of arrays or a list of
        tensors.
    """
    if isinstance(list_of_items[0], np.ndarray):
        result = np.concatenate(list_of_items)
        if indices is not None:
            if torch.is_tensor(indices[0]):
                indices = indices.cpu().numpy()
            result = result[indices]
    elif torch.is_tensor(list_of_items[0]):
        result = torch.cat(list_of_items)
        if indices is not None:
            result = result[indices]
    else:
        raise NotImplementedError(
            "cannot concatenate {}".format(type(list_of_items[0]))
        )

    return result


def extend(
    orig: Union[List, TensorType["..."]], new: Union[List, TensorType["..."]]
) -> Union[List, TensorType["..."]]:
    """
    Extends the original list or tensor with the new list or tensor.

    Returns
    -------
    Union[List, TensorType["..."]]
        Extended list or tensor.

    Raises
    ------
    NotImplementedError
        If the input type is not supported, i.e., not a list or a tensor.
    """
    assert isinstance(orig, type(new))
    if isinstance(orig, list):
        orig.extend(new)
    elif torch.tensor(orig):
        orig = torch.cat([orig, new])
    else:
        raise NotImplementedError(
            "Extension only supported for lists and torch tensors"
        )
    return orig


def copy(x: Union[List, TensorType["..."]]):
    """
    Makes copy of the input tensor or list.

    A tensor is cloned and detached from the computational graph.

    Parameters
    ----------
    x : Union[List, TensorType["..."]]
        Input tensor or list to be copied.

    Returns
    -------
    Union[List, TensorType["..."]]
        Copy of the input tensor or list.
    """
    if torch.is_tensor(x):
        return x.clone().detach()
    else:
        return deepcopy(x)


def bootstrap_samples(tensor, num_samples):
    """
    Bootstraps tensor along the last dimention
    returns tensor of the shape [initial_shape, num_samples]
    """
    dim_size = tensor.size(-1)
    bs_indices = torch.randint(
        0, dim_size, size=(num_samples * dim_size,), device=tensor.device
    )
    bs_samples = torch.index_select(tensor, -1, index=bs_indices)
    bs_samples = bs_samples.view(
        tensor.size()[:-1] + (num_samples, dim_size)
    ).transpose(-1, -2)
    return bs_samples


def example_documented_function(arg1, arg2):
    r"""Summary line: this function is not used anywhere, it's just an example.

    Extended description of function from the docstrings tutorial :ref:`write
    docstrings-extended`.

    Refer to

    * functions with :py:func:`gflownet.utils.common.set_device`
    * classes with :py:class:`gflownet.gflownet.GFlowNetAgent`
    * methods with :py:meth:`gflownet.envs.base.GFlowNetEnv.get_action_space`
    * constants with :py:const:`gflownet.envs.base.CMAP`

    Prepenend with ``~`` to refer to the name of the object only instead of the full
    path -> :py:func:`~gflownet.utils.common.set_device` will display as ``set_device``
    instead of the full path.

    Great maths:

    .. math::

        \int_0^1 x^2 dx = \frac{1}{3}

    .. important::

        A docstring with **math** MUST be a raw Python string (a string prepended with
        an ``r``: ``r"raw"``) to avoid backslashes being treated as escape characters.

        Alternatively, you can use double backslashes.

    .. warning::

        Display a warning. See :ref:`learn by example`. (<-- this is a cross reference,
        learn about it `here
        <https://www.sphinx-doc.org/en/master/usage/referencing.html#ref-rolel>`_)


    Examples
    --------
    >>> function(1, 'a')
    True
    >>> function(1, 2)
    True

    >>> function(1, 1)
    Traceback (most recent call last):
        ...

    Notes
    -----
    This block uses ``$ ... $`` for inline maths -> $e^{\frac{x}{2}}$.

    Or ``$$ ... $$`` for block math instead of the ``.. math:`` directive above.

    $$\int_0^1 x^2 dx = \frac{1}{3}$$


    Parameters
    ----------
    arg1 : int
        Description of arg1
    arg2 : str
        Description of arg2

    Returns
    -------
    bool
        Description of return value
    """
    if arg1 == arg2:
        raise ValueError("arg1 must not be equal to arg2")
    return True
