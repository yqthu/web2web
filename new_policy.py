from new_crawler import Crawler, aobject
from environment import Environment
import random
import yaml

class Policy:
    def __init__(self, config):
        self.env = Environment(config)

    def run(self):
        while True:
            print("New loop")
            state = self.env.reset()
            done = False
            while not done:
                action = self._get_action(state)
                state, reward, done, _ = self.env.step(action)

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

def main():
    with open('config.yaml') as f:
        config = yaml.load(f)
    policy = RandomPolicy(config)
    policy.run()

if __name__ == '__main__':
    main()