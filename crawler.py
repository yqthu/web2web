from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import MoveTargetOutOfBoundsException, NoSuchElementException
import selenium
from PIL import Image
import io
import json
import base64
import re

class MyChromeDriver(webdriver.Chrome):
    def send_cmd(self, cmd, params):
        resource = "/session/%s/chromium/send_command_and_get_result" % self.session_id
        url = self.command_executor._url + resource
        body = json.dumps({'cmd':cmd, 'params': params})
        response = self.command_executor._request('POST', url, body)
        return response.get('value')

def my_response_interceptor(request, response):
    headers = {k.lower(): v for k, v in response.headers.items()}
    headers['content-security-policy'] = ''
    response.headers = headers

class Crawler:
    def __init__(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--allow-file-access-from-files")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_experimental_option("mobileEmulation", {
            "deviceName": "Nexus 5",
            # "deviceMetrics": {"width": 1080, "height": 1920},
            # "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36"
            })
        prefs = {}
        prefs["profile.default_content_settings.popups"]=0
        prefs["download.default_directory"]='/tmp'
        chrome_options.add_experimental_option("prefs", prefs)
        self.driver = MyChromeDriver(options=chrome_options)
        self.driver.response_interceptor = my_response_interceptor
        self.driver.set_window_size(360,640)
        self.driver.implicitly_wait(10)

    def _get_element_at_coordinate(self, x, y):
        return self.driver.execute_script(
            'return document.elementFromPoint(arguments[0], arguments[1]);',
            x, y)

    def _get_weight_height(self):
        viewport = self.driver.send_cmd('Page.getLayoutMetrics', {})['visualViewport']
        return viewport['clientWidth'], viewport['clientHeight']

    def _convert_coordinate(self, x, y, allow_negative=False):
        if allow_negative:
            assert x >= -1 and x <= 1
            assert y >= -1 and y <= 1
        else:
            assert x >= 0 and x <= 1
            assert y >= 0 and y <= 1
        w, h = self._get_weight_height()
        return w*x, h*y

    def _set_overflow(self, rule):
        # for rule in tinycss2.parse_declaration_list(old_style):
        #     if type(rule) is tinycss2.ast.Declaration and rule.name == 'overflow':
        #         self._set_overflow(rule)
        assert rule.name == 'overflow'
        for thing in rule.value:
            if type(thing) is tinycss2.ast.IdentToken:
                thing.value = 'visible'
                rule.important = True
                return rule
        assert False, "overflow has no value?"

    def _enable_scroll(self):
        for el in map(self.driver.find_element_by_css_selector, ['body', 'html']):
            old_style = el.get_attribute('style')
            if old_style:
                style = re.sub('overflow:.+?;', 'overflow: visible !important;', old_style)
                self.driver.execute_script(f"""
                    arguments[0].setAttribute('style', '{style}');
                """, el)

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

    def onload(self):
        self._enable_scroll()
        with open('seg/seg.css') as f:
            cmd = f"""var seg_css = document.createElement('style');
            seg_css.innerHTML = `{f.read()}`
            document.head.appendChild(seg_css);
        """
        self.driver.execute_script(cmd)
        self.driver.execute_script("""
            var seg_js = document.createElement('script');
            seg_js.setAttribute('src', 'http://localhost:8000/seg/seg.js');
            document.head.appendChild(seg_js);
        """)
        self.scroll('DOWN')
        self.scroll('UP')

    def get_url(self, url):
        ret = self.driver.get(url)
        self.onload()
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
        ret = self.driver.send_cmd(
            'Input.synthesizeTapGesture', {'x': x, 'y': y}
        )
        self.onload()
        return ret

    def click_element(self, el):
        try:
            ret = ActionChains(self.driver).move_to_element(el).click().perform()
            self.onload()
            return ret
        except selenium.common.exceptions.JavascriptException:
            pass
        except selenium.common.exceptions.StaleElementReferenceException:
            pass
        except selenium.common.exceptions.MoveTargetOutOfBoundsException:
            pass

    def _scroll(self, x, y):
        x, y = self._convert_coordinate(x, y, allow_negative=True)
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
        response = self.driver.send_cmd('Page.captureScreenshot', {})['data']
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

    def type_word(self, word):
        return self.driver.send_cmd(
            'Input.insertText',
            {'text': word}
        )

    def close_popup(self):
        try:
            element = self.driver.find_element_by_css_selector("button[aria-label=关闭]")
        except NoSuchElementException:
            element = self.driver.find_elements_by_css_selector('.ModalWrap-itemBtn')[1]
        return self.click_element(element)
            # return ActionChains(self.driver).move_to_element(element).click().perform()

    def highlight_with_selector(self, selector):
        doc_node = crawler.driver.send_cmd('DOM.getDocument', {})
        for node_id in crawler.driver.send_cmd('DOM.querySelectorAll',
                {'nodeId': doc_node['root']['nodeId'], 'selector': selector})['nodeIds']:
            quad = crawler.driver.send_cmd('DOM.getBoxModel', {'nodeId': node_id})

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
    import pdb; pdb.set_trace()
