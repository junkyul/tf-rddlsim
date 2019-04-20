import json
import itertools
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from tensorflow.python.tools import inspect_checkpoint as chkp
import sys

import rddlgym

from tfmdp.policy.feedforward import FeedforwardPolicy



def get_fluents(compiler, fluents):
    with tf.Session(graph=compiler.graph) as sess:
        return { name: sess.run(fluent.tensor) for name, fluent in fluents }


def get_grid(non_fluents, initial_state):
    grid = {}
    grid['start'] = initial_state['location/1']
    grid['end'] = non_fluents['GOAL/1']
    grid['zones'] = []
    for (x, y), decay in zip(non_fluents['DECELERATION_ZONE_CENTER/2'], non_fluents['DECELERATION_ZONE_DECAY/1']):
        grid['zones'].append((x, y, decay))
    return grid


def get_policy(compiler, config):
    with open(config, 'r') as file:
        config = file.read()
    policy = FeedforwardPolicy.from_json(compiler, config)
    policy.build()
    return policy


def get_states(compiler, grid, npoints=100):
    states = []
    grid_x = np.linspace(grid[0], grid[1], npoints)
    grid_y = np.linspace(grid[2], grid[3], npoints)
    for (x, y) in itertools.product(grid_x, grid_y):
        states.append([x, y])

    with compiler.graph.as_default():
        states = (tf.constant(states, dtype=tf.float32, name='location'), )
        return states


def get_actions(compiler, policy, states):
    with compiler.graph.as_default():
        with tf.variable_scope('rnn'):
            timesteps = None
            actions = policy(states, timesteps)
            return actions


def evaluate(compiler, policy, states, actions):
    with tf.Session(graph=compiler.graph) as sess:
        policy.restore(sess, checkpoint)
        return sess.run([states[0], actions[0]])


def plot_policy_field(ax, grid, states_, actions_):
    plot_grid(ax, grid['size'])
    plot_deceleration_zones(ax, grid['size'], grid['zones'])
    plot_action_field(ax, states_, actions_)
    plot_states(ax, states_)
    plot_start_and_end_positions(ax, grid['start'], grid['end'])


def plot_policy_stream(ax, grid, states_, actions_):
    plot_grid(ax, grid['size'])
    plot_deceleration_zones(ax, grid['size'], grid['zones'])
    plot_action_stream(ax, states_, actions_)
    # plot_states(ax, states_)
    plot_start_and_end_positions(ax, grid['start'], grid['end'])


def plot_grid(ax, size):
    delta_x, delta_y = size[1] - size[0], size[3] - size[2]
    size_x = [size[0] - 0.10 * delta_x, size[1] + 0.10 * delta_x]
    size_y = [size[2] - 0.10 * delta_x, size[3] + 0.10 * delta_x]
    ax.axis(size_x + size_y)
    ax.set_aspect('equal')
    ax.set_xlabel('x coordinate')
    ax.set_ylabel('y coordinate')
    ax.grid()


def plot_start_and_end_positions(ax, start, end):
    ax.plot([start[0]], [start[1]], marker='X', markersize=15, color='limegreen', label='initial')
    ax.plot([end[0]],   [end[1]],   marker='X', markersize=15, color='crimson',   label='goal')


def plot_states(ax, states):
    [x, y] = np.split(states, 2, axis=1)
    ax.scatter(x, y, marker=".", c="dodgerblue", linewidths="1", alpha=0.5)


def plot_action_field(ax, states, actions):
    [x, y] = np.split(states, 2, axis=1)
    [a_x, a_y] = np.split(actions, 2, axis=1)
    ax.quiver(x, y, a_x, a_y,
              angles='xy', scale_units='xy', scale=1, color='dodgerblue', width=0.005, alpha=0.7)


def plot_action_stream(ax, states, actions):
    x, y = np.split(states, 2, axis=1)
    a_x, a_y = np.split(actions, 2, axis=1)

    points = int(np.sqrt(len(states)))
    x = x.reshape((points, points)).T
    y = y.reshape((points, points)).T

    a_x = a_x.reshape((points, points)).T
    a_y = a_y.reshape((points, points)).T

    # ax.streamplot(x, y, a_x, a_y, color='grey', density=1.2)
    ax.streamplot(x, y, a_x, a_y, color=(0.2, 0.0, 0.7, 0.4), density=1.2)


def plot_deceleration_zones(ax, size, zones, npoints=1000):
    X, Y = np.meshgrid(np.linspace(size[0], size[1], npoints), np.linspace(size[2], size[3], npoints))
    Lambda = 1.0
    for xcenter, ycenter, decay in zones:
        D = np.sqrt((X - xcenter) ** 2 + (Y - ycenter) ** 2)
        Lambda *= 2 / (1 + np.exp(- decay * D)) - 1.00
    ticks = np.arange(0.0, 1.01, 0.10)
    cp = ax.contourf(X, Y, Lambda, ticks, cmap=plt.cm.bone)
    # ax.set_colorbar(cp, ticks=ticks)
    cp = ax.contour(X, Y, Lambda, ticks, colors="black", linestyles="dashed")


# chkp.print_tensors_in_checkpoint_file(checkpoint, '', all_tensors=True, all_tensor_names=True)


if __name__ == '__main__':
    rddl = sys.argv[1]
    config = sys.argv[2]
    checkpoint = sys.argv[3]
    size = list(map(float, sys.argv[4].split(',')))
    npoints = float(sys.argv[5])

    compiler = rddlgym.make(rddl, mode=rddlgym.SCG)
    compiler.batch_mode_on()

    non_fluents = get_fluents(compiler, compiler.compile_non_fluents())
    initial_state = get_fluents(compiler, compiler.compile_initial_state())

    grid = get_grid(non_fluents, initial_state)
    grid['size'] = size
    
    policy = get_policy(compiler, config)

    states = get_states(compiler, grid['size'], npoints=npoints)
    actions = get_actions(compiler, policy, states)

    states_, actions_ = evaluate(compiler, policy, states, actions)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    plot_policy_field(ax1, grid, states_, actions_)
    plot_policy_stream(ax2, grid, states_, actions_)
    plt.show()


# python3 plot_navigation_policy.py Navigation-v2 drp.config.json drp.ckpt -5.0,11.0,-2.0,11.0 10
