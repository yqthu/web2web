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

class AsyncEnvironment(aobject, gym.Env):
    __actions = OrderedDict([
        ('act', ['click', 'scroll', 'press', 'type', 'back', 'reset', 'wait']),
        ('x', range(360 // 5)),
        ('y', range(640 // 5)),
        ('key', ['Enter', 'Space']),
        ('word', string.ascii_lowercase+string.digits),
        ('strength', range(8)),
        ('x_scroll_direction', ['left', 'right']),
        ('y_scroll_direction', ['up', 'down'])
    ])
    async def __init__(self, config, id):
        await super(AsyncEnvironment, self).__init__()
        self.crawler = await Crawler(config)
        self.start_url = config['start_url']
        self.max_steps = config['max_steps']
        self.x_grain, self.y_grain = config['action']['x_grain'], config['action']['y_grain']
        self.id = id
        self.observation_space = gym.spaces.Box(low=0, high=255, shape=(640, 360, 4), dtype=np.uint8)
        self.action_space = gym.spaces.MultiDiscrete(list(map(len, self.__actions.values())))

    async def reset(self):
        await self.crawler.reset()
        await self.crawler.goto(self.start_url)
        self.history_screenshot = []
        self.history_url = []
        state = await self.crawler.get_state()
        self.step_count = 0
        return self.crawler.get_screenshot_from_state(state)

    async def step(self, action):
        logging.info(f"async step: {self.step_count}")
        try:
            ret = await self._step(action)
            self.step_count += 1
            return ret
        except (pyppeteer.errors.NetworkError, pyppeteer.errors.PageError) as e:
            logging.warning(e)
            return await self._step_reset()
        except pyppeteer.errors.ElementHandleError as e:
            logging.warning(e)
            import pdb; pdb.set_trace()
            return await self._step_reset()

    async def _step_reset(self):
        obs = await self.reset()
        reward = 0.
        done = True
        info = {}
        return obs, reward, done, info

    async def _step(self, action):
        action = self._decode_action(action)
        act = action['act']
        if act == 'wait':
            await asyncio.sleep(0.5 * action['strength'])
        elif act == 'click':
            await self.crawler.click_at(action['x'] / self.x_grain, action['y'] / self.y_grain)
        elif act == 'press':
            await self.crawler.press(action['key'])
        elif act == 'type':
            await self.crawler.type(action['word'])
        elif act == 'back':
            if self.crawler.page.url == self.start_url:
                return await self._step_reset()
            else:
                print(self.crawler.page.url)
                await self.crawler.back()
        elif act == 'reset':
            await self.reset()
        elif act == 'scroll':
            x_dir = 1 if action['x_scroll_direction'] == 'right' else -1
            y_dir = 1 if action['y_scroll_direction'] == 'up' else -1
            await self.crawler.scroll(x_dir, y_dir, action['strength'])
        else:
            raise ValueError(f"Unknown action {act}")
        return await self._step_return()

    def _decode_action(self, action):
        return {k: v[a] for a, (k, v) in zip(action, self.__actions.items())}

    async def _step_return(self):
        state = await self.crawler.get_state()
        observation = self.crawler.get_screenshot_from_state(state)
        reward = self._get_reward(state)
        # done = len(self.history_screenshot) >= self.max_steps
        done = self.step_count >= self.max_steps
        if isinstance(observation, tuple):
            import pdb; pdb.set_trace()
        return observation, reward, done, {}

    def _get_reward(self, state):
        screenshot = state['screenshot']
        # TODO: PCA
        screenshot_encoding = screenshot[:10, :10, 0].reshape(-1)
        if state['url'] not in self.history_url:
            reward = 1.0
        elif not self.history_url:
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
        return ret

    def step_async(self, actions):
        self.actions = actions

    def step_wait(self):
        obs, rewards, dones, info = zip(*self._run([env.step(a) for env, a in zip(self.envs, self.actions)]))
        obs = np.stack(obs)
        return obs, rewards, dones, info

    def _run(self, aws):
        return self.loop.run_until_complete(asyncio.gather(*aws))

    def render(self, mode):
        return self._run([env.render(mode=mode) for env in self.envs])

    def close(self):
        return self._run([env.close() for env in self.envs])

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S',
        level=logging.INFO)
    logger = logging.getLogger(__name__)

    with open('config.yaml') as f:
        config = yaml.load(f)
    env = AsyncVecEnv(config)
    # from stable_baselines3.common.env_checker import check_env
    # check_env(env)
    model = PPO('MlpPolicy', env, verbose=1)
    model.learn(total_timesteps=10000)