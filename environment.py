from new_crawler import Crawler, aobject
import random
import yaml
import asyncio
import string
import numpy as np
import gym
from collections import OrderedDict
import pyppeteer
import logging
from stable_baselines3.common.vec_env import VecEnv, DummyVecEnv
from stable_baselines3 import PPO
from byol_extractor import ByolCNN
import torch
import traceback
import sys
import re

class AsyncEnvironment(aobject, gym.Env):
    __actions = OrderedDict([
        ('act', ['click', 'scroll', 'press', 'type', 'back', 'reset', 'wait']),
        ('x', range(360 // 5)),
        ('y', range(640 // 5)),
        ('key', ['Enter', 'Backspace', 'Escape', 'Tab',
            'ArrowLeft', 'ArrowRight', 'ArrowDown', 'ArrowUp']),
        ('word', string.ascii_lowercase+string.digits),
        ('strength', range(8)),
        ('x_scroll_direction', ['left', 'right']),
        ('y_scroll_direction', ['up', 'down'])
    ])
    async def __init__(self, config, id):
        await super(AsyncEnvironment, self).__init__()
        self.crawler = await Crawler(config)
        self.start_urls = config['start_urls']
        self.max_steps = config['max_steps']
        self.x_grain, self.y_grain = config['action']['x_grain'], config['action']['y_grain']
        self.id = id
        self.observation_space = gym.spaces.Box(low=0, high=255, shape=(640, 360, 3), dtype=np.uint8)
        self.action_space = gym.spaces.MultiDiscrete(list(map(len, self.__actions.values())))
        self.timeout = config['reset_browser_timeout'] // 1000

    async def reset(self):
        await self.crawler.reset()
        # if hasattr(self, 'start_url') and re.split('[?#]', self.crawler.page.url)[0] != self.start_url:
        #     logging.warning(f"[{self.id}] Mismatched start_url with page.url: {self.start_url, re.split('[?#]', self.crawler.page.url)[0]}")
        self.start_url = random.choice(self.start_urls)
        await self.crawler.goto(self.start_url)
        self.history_screenshot = []
        self.history_url = []
        self.step_count = 0
        state = await self.crawler.get_state()
        return self.crawler.get_screenshot_from_state(state)

    async def step(self, action):
        ret, succeed = await self.__reset_if_timeout(self._step(action))
        if succeed:
            logging.info(f"[{self.id}] async step: {self.step_count} - {ret[1]:.05f} - {ret[2]}")
            self.step_count += 1
        return ret

    async def __reset_if_timeout(self, awaitable):
        try:
            return (await asyncio.wait_for(awaitable, timeout=self.timeout), True)
        except (pyppeteer.errors.PageError,
                pyppeteer.errors.ElementHandleError) as e:
            logging.error(f"<{self.id}> {e}")
            logging.error(traceback.format_exc())
            logging.error(sys.exc_info()[2])
            return (await self._step_reset(), False)
        except (pyppeteer.errors.NetworkError,
                asyncio.TimeoutError,
                asyncio.base_futures.InvalidStateError) as e:
            logging.error(f"<{self.id}> {e}")
            logging.error(traceback.format_exc())
            logging.error(sys.exc_info()[2])
            logging.warning("Resetting Browser...")
            await self.crawler.reset_browser()
            return (await self._step_reset(), False)

    async def _step_reset(self):
        obs = await self.reset()
        reward = 0.
        done = True
        info = {}
        return obs, reward, done, info

    async def _step(self, action):
        action = self._decode_action(action)
        logging.info(f"[{self.id}] {action}")
        logging.info(f"[{self.id}] {(len(self.history_screenshot), len(self.history_url))}")
        act = action['act']
        no_reward = False
        # if self.step_count > 3:
        #     await self.crawler.goto('chrome://crash')
        if act == 'wait':
            await asyncio.sleep(0.5 * action['strength'])
        elif act == 'click':
            await self.crawler.click_at(action['x'] / self.x_grain, action['y'] / self.y_grain)
        elif act == 'press':
            await self.crawler.press(action['key'])
        elif act == 'type':
            await self.crawler.type(action['word'])
        elif act == 'back':
            if re.split('[?#]', self.crawler.page.url)[0] == self.start_url:
                # do nothing if already in start_url
                pass
            else:
                logging.info(f"[{self.id}] back() from {self.crawler.page.url}")
                await self.crawler.back()
            no_reward = True
        elif act == 'reset':
            # goto start_url, episode is continued
            await self.crawler.reset()
            await self.crawler.goto(self.start_url)
            no_reward = True
        elif act == 'scroll':
            x_dir = 1 if action['x_scroll_direction'] == 'right' else -1
            y_dir = 1 if action['y_scroll_direction'] == 'up' else -1
            await self.crawler.scroll(x_dir, y_dir, action['strength'])
        else:
            raise ValueError(f"Unknown action {act}")
        return await self._step_return(no_reward)

    def _decode_action(self, action):
        return {k: v[a] for a, (k, v) in zip(action, self.__actions.items())}

    async def _step_return(self, no_reward):
        state = await self.crawler.get_state()
        observation = self.crawler.get_screenshot_from_state(state)
        reward = 0. if no_reward else self._get_reward(state)
        # done = len(self.history_screenshot) >= self.max_steps
        done = (self.step_count == self.max_steps)
        assert self.step_count <= self.max_steps
        info = {}
        if done:
            info["terminal_observation"] = observation
            observation = await self.reset()
        return observation, reward, done, info

    def _get_reward(self, state):
        screenshot = state['screenshot']
        # TODO: PCA
        # screenshot_encoding = screenshot[:10, :10, 0].reshape(-1)
        screenshot_encoding = screenshot.reshape(-1)
        if not self.history_url:
            reward = 0.0
        else:
            calculate_reward = lambda x: ((screenshot_encoding - x) > 0.01).sum() / len(screenshot_encoding)
            nearest_screenshot = min(self.history_screenshot, key=calculate_reward)
            reward = calculate_reward(nearest_screenshot)
        self.history_screenshot.append(screenshot_encoding)
        self.history_url.append(state['url'])
        return reward

    async def render(self):
        return await self.crawler.page.screenshot()

    async def close(self):
        return await self.crawler.browser.close()

class AsyncVecEnv(DummyVecEnv):
    def __init__(self, config):
        self.loop = asyncio.get_event_loop()
        self.envs = self._run([AsyncEnvironment(config, i) for i in range(config['num_envs'])])
        self.action_space = self.envs[0].action_space
        self.observation_space = self.envs[0].observation_space
        self.num_envs = len(self.envs)

        self.actions = None

    def reset(self):
        ret = np.array(self._run([env.reset() for env in self.envs]))
        # try:
        #     np.transpose(ret, (0, 3, 1, 2))
        # except ValueError as e:
        #     logging.error(traceback.format_exc())
        #     logging.error(sys.exc_info()[2])
        #     import pdb; pdb.set_trace()
        return ret

    def step_async(self, actions):
        self.actions = actions

    def step_wait(self):
        obs, rewards, dones, info = zip(*self._run([env.step(a) for env, a in zip(self.envs, self.actions)]))
        obs = np.stack(obs)
        dones = np.array(dones)
        rewards = np.array(rewards)
        return obs, rewards, dones, info

    def _run(self, aws):
        return self.loop.run_until_complete(asyncio.gather(*aws))

    def render(self, mode):
        return self._run([env.render(mode=mode) for env in self.envs])

    def close(self):
        return self._run([env.close() for env in self.envs])

if __name__ == '__main__':
    with open('config.yaml') as f:
        config = yaml.load(f)
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S',
        filename=config['log_path'],
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    env = AsyncVecEnv(config)
    # from stable_baselines3.common.env_checker import check_env
    # check_env(env)
    model = PPO('MlpPolicy', env, verbose=1, n_steps=config['ppo_n_steps']
        , policy_kwargs={'features_extractor_class': ByolCNN}
    )
    try:
        model.load(config['policy_save_path'])
    except (FileNotFoundError, EOFError) as e:
        logging.warning(e)
    i = 0
    while True:
        logging.info(f"Epoch {i}")
        model.learn(total_timesteps=4096)
        model.save(config['policy_save_path'])
        logging.info(f"Saved to {config['policy_save_path']}")
        i += 1
