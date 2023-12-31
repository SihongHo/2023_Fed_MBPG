import torch
import garage
from garage.experiment import run_experiment
from garage.experiment import LocalRunner
from garage.np.baselines import LinearFeatureBaseline
from garage.tf.envs import TfEnv
from Policy import GaussianMLPPolicy, CategoricalMLPPolicy
from Algorithms.MBPG import MBPG_IM
from gym.envs.mujoco import Walker2dEnv, HopperEnv,HalfCheetahEnv
from gym.envs.classic_control import CartPoleEnv

from garage.envs import normalize
import copy

import argparse
parser = argparse.ArgumentParser(description='Avg_MBPG for DRL in mujoco')
parser.add_argument('--env', default='CartPole', type=str, help='choose environment from [CartPole, Walker, Hopper, HalfCheetah]')
parser.add_argument('--IS_MBPG_star', default=False, type=bool, help='whether to use IS-MBPG*')

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
    star_version = args.IS_MBPG_star
    if args.env == 'CartPole':
    #CartPole

        env = TfEnv(normalize(CartPoleEnv()))
        runner = LocalRunner(snapshot_config)
        batch_size = 5000
        max_length = 100
        n_timestep = 5e5
        n_counts = 5
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
        n_counts = 5
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
        n_counts = 5
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
        n_counts = 5
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

    # 初始化5个策略，它们一开始都是与初始策略相同
    policies = [copy.deepcopy(init_policy) for _ in range(num_policies)]

    # 循环num_global_iterations次
    for iteration in range(num_global_iterations):
        all_params = []

        # 对每个策略进行训练
        for policy in policies:
            baseline = LinearFeatureBaseline(env_spec=env.spec)
            algo = MBPG_IM(env_spec=env.spec,
                   env = env,
                   env_name= name,
                   policy=policy,
                   baseline=baseline,
                   max_path_length=max_length,
                   discount=discount,
                   grad_factor=grad_factor,
                   policy_lr= lr,
                   c = c,
                   w = w,
                   n_timestep=n_timestep,
                   #count=count,
                   th = th,
                   batch_size=batch_size,
                   center_adv=True,
                   g_max = g_max,
                   #decay_learning_rate=d_lr,
                   star_version=star_version
                   )
            runner.setup(algo, env)
            runner.train(n_epochs=num_local_iterations, batch_size=batch_size)

            # 保存这个策略的参数
            all_params.append(policy.state_dict())

        # 计算平均参数
        avg_params = {}
        for key in all_params[0].keys():
            avg_params[key] = sum([param[key] for param in all_params]) / num_policies

        # 更新每个策略的参数为平均参数
        for policy in policies:
            policy.load_state_dict(avg_params)

    # 这时，任意一个策略对象中都保存着最终的策略参数
    final_policy = policies[0]


run_experiment(
    run_task,
    snapshot_mode='last',
    seed=1,
)