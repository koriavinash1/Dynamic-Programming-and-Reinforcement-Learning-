# Finite-state MDP solved using Value Iteration
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import gym
import os
from gym import wrappers
import pickle
from collections import namedtuple
import dill
from time import time 


NUM_EPISODES = 5000
MAX_T = 10000
GAMMA   = 0.99  
EXPLORATION_RATE     = 1.0
MIN_EXPLORATION_RATE  = 0.2
EXPLORATION_RATE_DECAY = 0.010
episode_rewards = []
mean_reward = []
Train = True


OUTPUT_RESULTS_DIR = "../logs/IRL"
ENVIRONMENT = 'CartPole-v0'
# ENVIRONMENT = 'InvertedPendulum-v2'

# TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
TIMESTAMP = 'RESULTS'
# Hyperparameter
#Best found : num_bins_per_observation = 12 ; select_observations = lambda O: np.array([O[1],O[2],O[3]])
num_bins_per_observation = 9                                                                                                                                                                                                                                                                                                                # Could try different number of bins for the different dimensions

SUMMARY_DIR = os.path.join(OUTPUT_RESULTS_DIR, "ValueIteration-number_bins_"+str(num_bins_per_observation),\
                             ENVIRONMENT, TIMESTAMP)

if not os.path.exists(SUMMARY_DIR):
    os.makedirs(SUMMARY_DIR)

env = gym.make(ENVIRONMENT)
env._max_episode_steps = 100000

env = wrappers.Monitor(env, os.path.join(SUMMARY_DIR, ENVIRONMENT), force=True, video_callable=None)
# env.unwrapped()
# env.seed(1)

select_observations = lambda O: np.array([O[1],O[2],O[3]])
observation = env.reset()
observation = select_observations(observation)


observation_dimensions = np.size(observation)
try: num_actions = env.action_space.n
except: num_actions = env.action_space.shape[0]

observation_space_high = env.observation_space.high
observation_space_low = env.observation_space.low


num_states = num_bins_per_observation**observation_dimensions


###################################################################################################
#                                     descretizing funcitons                                      #
###################################################################################################
def moving_average(a, n=3) :
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n


def make_observation_bins(minV, maxV, num_bins):
    if(minV == -np.Inf) or (minV < -10e4):
        minV = -5 # Should really learn this const instead
    if(maxV == np.Inf) or (maxV > 10e4):
        maxV = 5
    bins = np.arange(minV, maxV, (float(maxV)-float(minV))/((num_bins - 2)))
    bins = np.sort(np.append(bins, [0])) # Ensure we split at 0
    return bins

observation_dimension_bins = []
for observation_dimension in range(observation_dimensions):
    observation_dimension_bins.append(make_observation_bins(observation_space_low[observation_dimension], 
                                observation_space_high[observation_dimension], 
                                num_bins_per_observation))
    
print("[INFO]: observation_dimension {} \n high : {} \n low : {}, \n \
        num_bins_per_observation: {}, \n observation_dimension_bins : {}".format(observation_dimensions,\
                                                                                observation_space_high,\
                                                                                observation_space_low,\
                                                                                num_bins_per_observation,\
                                                                                observation_dimension_bins))



###################################################################################################
#                                 state observation functions                                     #
###################################################################################################

def observation_to_state(observation):
    state = 0
    for observation_dimension in range(observation_dimensions):
        state = state + np.digitize(observation[observation_dimension],\
                observation_dimension_bins[observation_dimension])*\
                num_bins_per_observation**observation_dimension 
    return state
  
print("[INFO]: Min State: {} Max State: {} Num States: {}".format(observation_to_state([-10,-10,10,-10.5]), \
                                observation_to_state([10,10,10,10.5]),
                                num_states))




state_values = np.random.rand(num_states) * 0.1
state_rewards = np.zeros((num_states))
state_transition_probabilities = np.ones((num_states, num_states, num_actions)) / num_states
state_transition_counters = np.zeros((num_states, num_states, num_actions))




###################################################################################################
#                                 best action pickup functions                                    #
###################################################################################################


def pick_best_action(current_state, state_values, state_transition_probabilities, eval_ = False):
    best_action = -1
    best_action_value = -np.Inf
    for a_i in range(num_actions):
        action_value = state_transition_probabilities[current_state,:,a_i].dot(state_values)
        if eval_ or (action_value > best_action_value):
            best_action_value = action_value
            best_action = a_i
        elif (action_value == best_action_value):
            if np.random.randint(0,2) == 0:
                best_action = a_i
        
    return best_action


def update_state_transition_probabilities_from_counters(probabilities, counters):
    for a_i in range(num_actions):
        for s_i in range(num_states):
            total_transitions_out_of_state = np.sum(counters[s_i,:,a_i])
            if(total_transitions_out_of_state > 0):
                probabilities[s_i,:,a_i] = counters[s_i,:,a_i] / total_transitions_out_of_state
        
    return probabilities




def run_value_iteration(state_values, state_transition_probabilities, state_rewards):
    GAMMA = 0.9
    convergence_tolerance = 1e-6
    iteration = 0
    max_dif = np.Inf
    while max_dif > convergence_tolerance:  
        iteration = iteration + 1
        old_state_values = np.copy(state_values)

        best_action_values = np.zeros((num_states)) - np.Inf

        for a_i in range(num_actions):
            best_action_values = np.maximum(best_action_values,\
                        state_transition_probabilities[:,:,a_i].dot(state_values))

        state_values = state_rewards + GAMMA * best_action_values
        max_dif = np.max(np.abs(state_values - old_state_values))       
        
        # print("[INFO ValueIteration]============================")
        # print("Max Value Difference: ", max_dif)
    return state_values
    
      


###################################################################################################
#                                        iterate loops                                            #
###################################################################################################


if Train:
    for i_episode in range(NUM_EPISODES):
        current_observation = env.reset()
        current_observation = select_observations(current_observation)
        current_state = observation_to_state(current_observation)

        episode_reward = 0
        env.render()
        if i_episode % 50 == 49: EXPLORATION_RATE = max(MIN_EXPLORATION_RATE, EXPLORATION_RATE * 0.1)

        if np.random.uniform() <= EXPLORATION_RATE: current_state = np.random.randint(0, num_states, 1)

        for t in range(MAX_T):
            action = pick_best_action(current_state, state_values, state_transition_probabilities)

            old_state = current_state
            observation, reward, done, info = env.step(action)
            observation = select_observations(observation)
            current_state = observation_to_state(observation)
            

            state_transition_counters[old_state, current_state, action] += 1

            episode_reward = episode_reward + reward        
            st_time = time()
            if not done:
                state_rewards[current_state] = 0.1            
            elif done or t == MAX_T-1:
                episode_rewards.append(episode_reward)
                mean_reward.append(np.mean(episode_rewards))
                print("[INFO Data {}]============================".format(t))
                print("Episode: ", i_episode)
                print("Reward: ", episode_reward)
                print("Mean Reward: ", np.mean(episode_rewards))
                print("Max reward so far: ", max(episode_rewards))

                
                # Average length of episode is > 195, anything less than than 195 has -ve reward
                # state_rewards[current_state] = (-1 if(t < 95) else +1)
                # state_rewards[current_state] = (-1 if(t < MAX_T - 100) else +1)
                # state_rewards[current_state] = (-1*MAX_T/(t+1) if(t < MAX_T) else +1)
                # state_rewards[current_state] = t
                if t < 195:
                  state_rewards[current_state] = -1
                elif t < 300:
                  state_rewards[current_state] = 1 
                else:
                  state_rewards[current_state] =2

                state_transition_probabilities = \
                    update_state_transition_probabilities_from_counters(state_transition_probabilities,\
                                                state_transition_counters)
                state_values = run_value_iteration(state_values, state_transition_probabilities, state_rewards)
                env.close()
                break


        if i_episode % 20 == 19:
            print(np.sum(state_rewards))
            print("State Values:",np.sum(state_values))
            print("[INFO] Model Saved State Rewards: ", state_rewards)
            np.save(os.path.join(SUMMARY_DIR, 'state_values.npy') , state_values)
            np.save(os.path.join(SUMMARY_DIR, 'state_rewards.npy') , state_rewards)
            np.save(os.path.join(SUMMARY_DIR, 'state_transition_probabilities.npy') , state_transition_probabilities)


    episode_rewards = moving_average(episode_rewards, n = 50)
    episode_rewards[0] = mean_reward[30]
    plt.plot(episode_rewards)
    plt.plot(mean_reward[30:])
    plt.title('Value Iteration Reward Convergence for 5 Bins')
    plt.legend(['Episode reward with smoothening widow of n = 25', 'Mean episode reward'])
    plt.ylabel('Reward')
    plt.xlabel('Iteration')
    plt.show()

else:

    ##########################################################################
    #                         Model Evaluation                               #
    ##########################################################################
    state_values = np.load(os.path.join(SUMMARY_DIR, 'state_values.npy'))
    state_transition_probabilities = np.load(os.path.join(SUMMARY_DIR, 'state_transition_probabilities.npy'))
    # env.seed(1)
    env.render()
    current_observation = env.reset()
    current_observation = select_observations(current_observation)
    current_state = observation_to_state(current_observation)
    episode_reward = 0
    
    while True:
        action = pick_best_action(current_state, state_values, state_transition_probabilities)
        old_state = current_state
        observation, reward, done, info = env.step(action)
        episode_reward = episode_reward + reward
        current_state = observation_to_state(select_observations(observation))
        if done: break

    print ("[INFO] Final evaluation reward: {}".format(episode_reward))
    env.close()

## Code to write details for LP IRL

# print("Writing File ....")
# policy = np.array([pick_best_action(i,state_values,state_transition_probabilities) for i in range(num_states)])
# print(policy[1:10])
# path = "/home/hari/Acads/RL/IRL/cartpole_irl/"
# filename = "ARGS1.txt"
# file = open(path+filename,"wb")
# args = [state_transition_probabilities,policy,state_rewards]
# pickle.dump(args,file,protocol=2)
# file.close()



## Code to write details for Maxent_IRL


print("Writing File...")

def generate_demonstrations(n_trajs=10, len_traj=500):

  """gatheres expert demonstrations

  inputs:
  gw          Gridworld - the environment
  policy      Nx1 matrix
  n_trajs     int - number of trajectories to generate
  rand_start  bool - randomly picking start position or not
  start_pos   2x1 list - set start position, default [0,0]
  returns:
  trajs       a list of trajectories - each element in the list is a list of Steps representing an episode
  """
  Step = namedtuple('Step','cur_state action next_state reward done')
  Step.__module__ = '__main__'
  trajs = []
  for i in range(n_trajs):
  	episode = []
  	current_observation = env.reset() 
  	current_observation = select_observations(current_observation)
  	current_state = observation_to_state(current_observation)
  	action = pick_best_action(current_state,state_values,state_transition_probabilities)
  	next_state, reward, is_done,info = env.step(action)
  	#episode.append(namedtuple(cur_state=current_state, action=action, next_state=observation_to_state(select_observations(next_state)), reward=reward, done=is_done))
  	episode.append(tuple([current_state,action,observation_to_state(select_observations(next_state)),reward,is_done]))
  	for _ in range(len_traj):
  		current_observation = select_observations(next_state)
  		current_state = observation_to_state(current_observation)
  		action = pick_best_action(current_state,state_values,state_transition_probabilities)
  		next_state, reward, is_done,info = env.step(action)
  		episode.append(tuple([current_state,action,observation_to_state(select_observations(next_state)),reward,is_done]))
  		#episode.append(namedtuple(cur_state=current_state, action=action, next_state=observation_to_state(select_observations(next_state)), reward=reward, done=is_done))
  		if is_done:
  			break
  	trajs.append(episode)
  return trajs

path = "/home/hari/Github_repo/Dynamic-Programming-and-Reinforcement-Learning/FinalProject/logs/IRL/Max_entropy/"
#filename = "ARGS_max_entropy.txt"

#file = open(path+filename,"wb")
np.save(path+'Trans_prob',state_transition_probabilities)
np.save(path+'Trajs',generate_demonstrations(),allow_pickle=True)
np.save(path+'Rewards_Gt',state_rewards)
#args = [state_transition_probabilities,generate_demonstrations(),state_rewards]
#pickle.dump(args,file,protocol=2)
#file.close()
