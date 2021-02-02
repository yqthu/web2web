from new_crawler import Crawler, aobject
from environment import Environment
import random
import yaml
import asyncio

class Policy(aobject):
    async def __init__(self, config):
        self.envs = [(await Environment(config)) for _ in range(config['num_envs'])]

    async def _run(self, env):
        while True:
            print("New loop")
            state = await env.reset()
            done = False
            while not done:
                action = self._get_action(state)
                state, reward, done, _ = await env.step(action)

    async def run(self):
        await asyncio.gather(*map(self._run, self.envs))

class RandomPolicy(Policy):
    # (act, x, y, key, word, strength, x_scroll_direction, y_scroll_direction)
    def _get_action(self, state):
        ret = {
            'act': 'wait',
            'x': 0.3,
            'y': 0.5,
            'key': 'Enter',
            'word': 'TestWord',
            'strength': 5,
            'x_scroll_direction': 'right',
            'y_scroll_direction': 'down'
        }
        return ret

async def main():
    with open('config.yaml') as f:
        config = yaml.load(f)
    policy = await RandomPolicy(config)
    await policy.run()

if __name__ == '__main__':
    asyncio.run(main()) #, debug=True)