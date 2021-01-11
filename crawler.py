from selenium import webdriver  
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import MoveTargetOutOfBoundsException
from PIL import Image
import io

class Crawler:
    def __init__(self, url):
        # chrome_options = Options() 
        # # chrome_options.add_argument("--headless")
        # chrome_options.add_experimental_option("mobileEmulation", { "deviceName"
        # : "Nexus 5"}) 
        # self.driver = webdriver.Chrome(options=chrome_options)
        user_agent = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_0 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7A341 Safari/528.16"
        profile = webdriver.FirefoxProfile()
        profile.set_preference("general.useragent.override", user_agent)
        # firefox_options.set_capability("deviceName", "iPhone")
        self.driver = webdriver.Firefox(profile)
        self.driver.set_window_size(360,640)
        # self.driver.implicitly_wait(3)
        self.url = url

    def count_clickable(self):
        self.driver.get(self.url)
        seen_elements = set()
        # el = self.driver.switch_to.active_element
        el = self.driver.find_element_by_xpath("//body")
        import pdb; pdb.set_trace()
        while True:
            el.send_keys(Keys.TAB)
            # el.send_keys(Keys.ENTER)
            if el in seen_elements:
                return len(seen_elements)
            seen_elements.add(el)

    def get_element_at_coordinate(x, y):
        return self.driver.execute_script(
            'return document.elementFromPoint(arguments[0], arguments[1]);',
            x, y)

    def get_zoom(self):
        zoom = self.driver.execute_script('return document.body.style.zoom')
        if zoom:
            return float(zoom)
        else:
            return 1.0

    def get_url(self, url):
        ret = self.driver.get(url)
        self.enable_pinch_zoom()
        return ret

    def enable_pinch_zoom(self):
        content = 'width=device-width, initial-scale=1., maximum-scale=12.0, minimum-scale=.25, user-scalable=yes'
        try:
            element = self.driver.find_element_by_css_selector('head > meta[name=viewport]')
            self.driver.execute_script(f"""
                arguments[0].setAttribute('content', '{content}');
            """, element)
        except selenium.common.exceptions.NoSuchElementException:
            head = self.driver.find_element_by_css_selector('head')
            self.driver.execute_script(f"""
                var meta = document.createElement('meta');
                meta.name = viewport;
                meta.content = '{content}';
                arguments[0].appendChild(meta);
            """, head)

    def zoom_in(self):
        zoom = float(self.driver.execute_script('return document.body.style.zoom'))
        self.driver.execute_script(f'document.body.style.zoom = {self.get_zoom()+0.1}')

    def zoom_out(self):
        zoom = float(self.driver.execute_script('return document.body.style.zoom'))
        self.driver.execute_script(f'document.body.style.zoom = {self.get_zoom()-0.1}')

    def pinch_zoom(self):
        ActionChains(self.driver).key_down(Keys.SHIFT).move_by_offset(100, 100).click_and_hold().move_by_offset(100, 200).release().key_up(Keys.SHIFT).perform()

    def zoom(self, x: float, y: float, scale: float):
        assert x >= 0 and x <= 1
        assert y >= 0 and y <= 1
        self.driver.execute_script("document.body.style.MozTransformOrigin=arguments[0];" "document.body.style.MozTransform=arguments[1]; ", f'{x*100}% {y*100}%', f'scale({scale})')

    def get_all_tab_screeshots(self):
        n_elements = self.count_clickable()
        print(f"Get {n_elements} clickable elements")
        for i in range(n_elements):
            self.get_url(url)
            el = self.driver.find_element_by_xpath("//body")
            # el = self.driver.switch_to.active_element
            for _ in range(i):
                el.send_keys(Keys.TAB)
            # el.click()
            self.click_element(el)
            yield Image.open(io.BytesIO(el.screenshot_as_png))

    def click_element(self, element):
        actions = ActionChains(self.driver)
        actions.move_to_element(element)
        actions.click(element)
        actions.perform()
        # return Image.open(io.BytesIO(element.screenshot_as_png))

if __name__ == '__main__':
    # url = "https://www.baidu.com"
    # url = "http://www.stats.gov.cn/tjgz/tjdt/202101/W020210108515010680551_r75.jpg"
    url = "https://www.xuetangx.com"
    crawler = Crawler(url)
    for img in crawler.get_all_tab_screeshots():
        img.show()
        import pdb; pdb.set_trace()
