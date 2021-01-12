from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import MoveTargetOutOfBoundsException, NoSuchElementException
from PIL import Image
import io
import json
import base64

class MyChromeDriver(webdriver.Chrome):
    def send_cmd(self, cmd, params):
        resource = "/session/%s/chromium/send_command_and_get_result" % self.session_id
        url = self.command_executor._url + resource
        body = json.dumps({'cmd':cmd, 'params': params})
        response = self.command_executor._request('POST', url, body)
        return response.get('value')

class Crawler:
    def __init__(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_experimental_option("mobileEmulation", { "deviceName"
        : "Nexus 5"})
        self.driver = MyChromeDriver(options=chrome_options)
        self.driver.set_window_size(360,640)
        # self.driver.implicitly_wait(3)

    def _get_element_at_coordinate(self, x, y):
        return self.driver.execute_script(
            'return document.elementFromPoint(arguments[0], arguments[1]);',
            x, y)

    def _get_weight_height(self):
        viewport = self.driver.send_cmd('Page.getLayoutMetrics', {})['visualViewport']
        return viewport['clientWidth'], viewport['clientHeight']

    def _convert_coordinate(self, x, y):
        assert x >= 0 and x <= 1
        assert y >= 0 and y <= 1
        w, h = self._get_weight_height()
        return w*x, h*y

    def _enable_pinch_zoom(self):
        content = 'width=device-width, initial-scale=1., maximum-scale=12.0, minimum-scale=.25, user-scalable=yes'
        try:
            element = self.driver.find_element_by_css_selector('head > meta[name=viewport]')
            self.driver.execute_script(f"""
                arguments[0].setAttribute('content', '{content}');
            """, element)
        except NoSuchElementException:
            head = self.driver.find_element_by_css_selector('head')
            self.driver.execute_script(f"""
                var meta = document.createElement('meta');
                meta.name = 'viewport';
                meta.content = '{content}';
                arguments[0].appendChild(meta);
            """, head)

    def get_url(self, url):
        ret = self.driver.get(url)
        self._enable_pinch_zoom()
        self.zoom(0, 0, 0.1)
        # NOTE: always start from the upper left corner
        for _ in range(3):
            self.scroll('LEFT')
            self.scroll('UP')
        return ret

    def zoom(self, x: float, y: float, scale: float):
        x, y = self._convert_coordinate(x, y)
        return self.driver.send_cmd(
            'Input.synthesizePinchGesture',
            {'x': x, 'y': y, 'scaleFactor': scale}
        )

    def click_at(self, x: float, y: float):
        x, y = self._convert_coordinate(x, y)
        return self.driver.send_cmd(
            'Input.synthesizeTapGesture', {'x': x, 'y': y}
        )

    def _scroll(self, x, y):
        x, y = self._convert_coordinate(x, y)
        return self.driver.send_cmd(
            'Input.synthesizeScrollGesture', 
            {'x': 0, 'y': 0, 'xDistance': 0.3*x, 'yDistance': 0.3*y}
        )

    def scroll(self, direction):
        if direction == 'LEFT':
            # self.driver.execute_script(f"window.scrollBy(-{stride}, 0)")
            return self._scroll(1, 0)
        elif direction == 'RIGHT':
            return self._scroll(-1, 0)
        elif direction == 'UP':
            return self._scroll(0, 1)
        elif direction == 'DOWN':
            return self._scroll(0, -1)
        else:
            raise ValueError(f"Unknown direction {direction}")

    def _screenshot(self):
        response = crawler.driver.send_cmd('Page.captureScreenshot', {})['data']
        img_bytes = base64.b64decode(response)
        return Image.open(io.BytesIO(img_bytes))

    def screenshot(self):
        if len(self.driver.window_handles) == 1:
            return self._screenshot()
        elif len(self.driver.window_handles) == 2:
            self.driver.switch_to.window(self.driver.window_handles[1])
            ret = self._screenshot()
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return ret
        else:
            raise RuntimeError(f"Why do I get {len(self.driver.window_handles)} opening?")

if __name__ == '__main__':
    # url = "https://www.baidu.com"
    # url = "http://www.stats.gov.cn/tjgz/tjdt/202101/W020210108515010680551_r75.jpg"
    # url = "https://www.xuetangx.com"
    url = "http://info.tsinghua.edu.cn"
    crawler = Crawler()
    crawler.get_url(url)
    crawler.zoom(0.5, 0.5, 4)
    crawler.click_at(0.9, 0.25)
    crawler.screenshot().save('/tmp/info.png')
