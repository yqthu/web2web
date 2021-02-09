from new_crawler import Crawler, aobject
import random
import yaml
import asyncio
import numpy as np

class AsyncEnvironment(aobject):
    async def __init__(self, config, id):
        self.crawler = await Crawler(config)
        self.start_url = config['start_url']
        self.max_steps = config['max_steps']
        self.x_grain, self.y_grain = config['action']['x_grain'], config['action']['y_grain']
        self.id = id

    async def reset(self):
        await self.crawler.goto(self.start_url)
        self.history_screenshot = []
        self.history_url = []
        return await self.crawler.get_state()

    async def step(self, action):
        ''' action: (act, x, y, key, word, strength, x_scroll_direction, y_scroll_direction)
        act: ['click', 'scroll', 'press', 'type', 'back', 'reset', 'wait']
        x: range(360 / 5)
        y: range(640 / 5)
        key: shift/enter/space
        word: multiples of string.ascii_letters+string.digits
        strength: range(8)
        x_scroll_direction: ['left', 'right']
        y_scroll_direction: ['up', 'down']
        '''
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
            await self.crawler.page.goBack()
        elif act == 'reset':
            await self.reset()
        elif act == 'scroll':
            x_dir = 1 if action['x_scroll_direction'] == 'right' else -1
            y_dir = 1 if action['y_scroll_direction'] == 'up' else -1
            await self.crawler.scroll(x_dir, y_dir, action['strength'])
        else:
            raise ValueError(f"Unknown action {act}")
        return await self._step()

    async def _step(self):
        state = await self.crawler.get_state()
        reward = self._get_reward(state)
        done = len(self.history_screenshot) >= self.max_steps
        return state, reward, done, {}

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

class Environment:
    def __init__(self, config):
        self.loop = asyncio.get_event_loop()
        self.envs = self._run([AsyncEnvironment(config, i) for i in range(config['num_envs'])])

    def reset(self):
        return self._run([env.reset() for env in self.envs])

    def step(self, action):
        return tuple(zip(*self._run([env.step(action) for env in self.envs])))

    def _run(self, aws):
        return self.loop.run_until_complete(asyncio.gather(*aws))