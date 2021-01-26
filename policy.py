import selenium
from selenium.webdriver.common.action_chains import ActionChains
from PIL import ImageChops
from tqdm import tqdm
from crawler import Crawler
import numpy as np
import string
import random
import os
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Process

def img_equal(im1, im2):
    diff = np.array(im1) - np.array(im2)
    return np.linalg.norm(diff) == 0
    return ImageChops.difference(im1, im2).getbbox() is None

class Policy:
    def __init__(self, crawler, start_url):
        self.crawler = crawler
        self.start_url = start_url
        self.crawler.get_url(start_url)
        self.save_dir = 'imgs'
        os.makedirs(self.save_dir, exist_ok=True)

    def get_save_start_num(self):
        return len(os.listdir(self.save_dir))

    def run(self):
        current_screenshot = self.crawler.screenshot()
        while True:
            current_screenshot.save(f'{self.save_dir}/{self.get_save_start_num():06d}.png')
            current_screenshot = self.random_move(current_screenshot)

    def random_move(self, current_screenshot):
        step = 0
        while True:
            rnd = random.random()
            if rnd < 0.01 * step:
                if self.crawler.driver.current_url != self.start_url:
                    self.crawler.driver.back()
            elif rnd < 0.1:
                elements = self.crawler.driver.find_elements_by_xpath('//*')
                el = random.choice(elements)
                self.crawler.click_element(el)
            elif rnd < 0.2:
                self.crawler.click_at(random.random(), random.random())
            elif rnd < 0.5:
                scale = random.random()+1
                if random.random() < 0.5:
                    scale = 1 / scale
                self.crawler.zoom(random.random(), random.random(), scale)
            elif rnd < 0.8:
                self.crawler.type_word("".join([random.choice(string.digits+string.ascii_letters) for i in range(random.randint(1, 8))]))
            else:
                for _ in range(5):
                    self.crawler.scroll(random.choice(['LEFT', 'UP', 'DOWN', 'RIGHT']))
            sc = self.crawler.screenshot()
            if not img_equal(sc, current_screenshot):
                return sc
            step += 1

def run():
    url = "https://www.hao123.com/"
    url = "https://www.zhihu.com/"
    url = "https://www.zhihu.com/question/20384380"
    crawler = Crawler()
    policy = Policy(crawler, url)
    # crawler.close_popup()
    import pdb; pdb.set_trace()
    policy.run()


if __name__ == '__main__':
    # url = "https://www.xuetangx.com/"
    run()
    # processes = [Process(target=run) for _ in range(16)]
    # for p in processes:
    #     p.start()
    # for p in processes:
    #     p.join()
