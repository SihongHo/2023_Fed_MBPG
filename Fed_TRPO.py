import torch
import garage
from garage.experiment import run_experiment
from garage.experiment import LocalRunner
from garage.np.baselines import LinearFeatureBaseline
from garage.tf.envs import TfEnv
from garage.tf.algos import TRPO
from Policy import GaussianMLPPolicy, CategoricalMLPPolicy
from Algorithms.MBPG import MBPG_IM
from gym.envs.mujoco import Walker2dEnv, HopperEnv,HalfCheetahEnv
from gym.envs.classic_control import CartPoleEnv

from garage.envs import normalize
import copy

import argparse
parser = argparse.ArgumentParser(description='Fed_TRPO for DRL in mujoco')
parser.add_argument('--env', default='CartPole', type=str, help='choose environment from [CartPole, Walker, Hopper, HalfCheetah]')

args = parser.parse_args()

def run_task(snapshot_config, *_):
    """Set up environment and algorithm and run the task.
    Args:
        snapshot_config (garage.experiment.SnapshotConfig): The snapshot
            configuration used by LocalRunner to create the snapshotter.
            If None, it will create one with default settings.
        _ : Unused parameters
    """

    #count = 1
    th = 1.8
    g_max = 0.05
    if args.env == 'CartPole':
    #CartPole

        env = TfEnv(normalize(CartPoleEnv()))
        runner = LocalRunner(snapshot_config)
        batch_size = 5000
        max_length = 100
        n_timestep = 5e5
        name = 'CartPole'
        #grad_factor = 5
        grad_factor = 100
        th = 1.2
        # # batchsize:1
        # lr = 0.1
        # w = 1.5
        # c = 15

        #batchsize:50
        lr = 0.75
        c = 1
        w = 1

        # for MBPG+:
        # lr = 1.2

        #g_max = 0.03
        discount = 0.995
        path = './init/CartPole_policy.pth'

    if args.env == 'Walker':
        #Walker_2d
        env = TfEnv(normalize(Walker2dEnv()))
        runner = LocalRunner(snapshot_config)
        batch_size = 50000
        max_length = 500

        th = 1.2

        n_timestep = 1e7
        lr = 0.75
        w = 2
        c = 5
        grad_factor = 10

        # for MBPG+:
        #lr = 0.9

        discount = 0.999

        name = 'Walk'
        path = './init/Walk_policy.pth'

    if args.env == 'Hopper':
        #Hopper
        env = TfEnv(normalize(HopperEnv()))
        runner = LocalRunner(snapshot_config)

        batch_size = 50000

        max_length = 1000
        th = 1.5
        n_timestep = 1e7
        lr = 0.75
        w = 1
        c = 3
        grad_factor = 10
        g_max = 0.15
        discount = 0.999

        name = 'Hopper'
        path = './init/Hopper_policy.pth'

    if args.env == 'HalfCheetah':
        env = TfEnv(normalize(HalfCheetahEnv()))
        runner = LocalRunner(snapshot_config)
        batch_size = 10000
        #batch_size = 50000
        max_length = 500

        n_timestep = 1e7
        lr = 0.6
        w = 3
        c =7
        grad_factor = 10
        th = 1.2
        g_max = 0.06

        discount = 0.999

        name = 'HalfCheetah'
        path = './init/HalfCheetah_policy.pth'

    num_policies = 5
    num_global_iterations = 50
    num_local_iterations = 100
    global_lr = 0.6
    local_lr = lr
    coef = global_lr / (local_lr * num_policies * num_local_iterations)

    # 初始化一个初始策略，并保存其参数
    if args.env == 'CartPole':
        init_policy = CategoricalMLPPolicy(env.spec,
                                        hidden_sizes=[8, 8],
                                        hidden_nonlinearity=torch.tanh,
                                        output_nonlinearity=None)
    else:
        init_policy = GaussianMLPPolicy(env.spec,
                                        hidden_sizes=[64, 64],
                                        hidden_nonlinearity=torch.tanh,
                                        output_nonlinearity=None)

    init_policy_params = init_policy.state_dict()

    # 初始化5个策略，它们一开始都是与初始策略相同
    policies = [copy.deepcopy(init_policy) for _ in range(num_policies)]

    # 循环num_global_iterations次
    for iteration in range(num_global_iterations):
        total_diff_params = {k: torch.zeros_like(v) for k, v in init_policy_params.items()}

        # 对每个策略进行训练
        for policy in policies:
            baseline = LinearFeatureBaseline(env_spec=env.spec)
            algo = TRPO(env_spec=env.spec,
                    policy=policy,
                    baseline=baseline,
                    max_path_length=100,
                    discount=0.99,
                    max_kl_step=0.01)
            runner.setup(algo, env)
            runner.train(n_epochs=num_local_iterations, batch_size=batch_size)

            # 计算差值，并累加到总差值中
            for key in init_policy_params:
                diff = policy.state_dict()[key] - init_policy_params[key]
                total_diff_params[key] += diff

        # 使用初始策略的参数和总差值更新每个策略
        for policy in policies:
            updated_params = {k: init_policy_params[k] + coef * total_diff_params[k] for k in init_policy_params}
            policy.load_state_dict(updated_params)

    # 这时，任意一个策略对象中都保存着最终的策略参数
    final_policy = policies[0]


run_experiment(
    run_task,
    snapshot_mode='last',
    seed=1,
)