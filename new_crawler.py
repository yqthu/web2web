import asyncio
import pyppeteer
from PIL import Image
import io
import numpy as np
import cv2
import logging

class aobject(object):
    """
    https://stackoverflow.com/a/45364670/6134778
    Inheriting this class allows you to define an async __init__.
    So you can create objects by doing something like `await MyClass(params)`
    """
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def __init__(self):
        pass

class Crawler(aobject):
    async def __init__(self, config):
        self.id = config['id']
        self.timeout = config['timeout']
        await self.reset_browser()
        await self.reset()

    async def reset_browser(self):
        if hasattr(self, 'browser'):
            await self.browser.close()
        while True:
            try:
                self.browser = await pyppeteer.launch({
                    'ignoreHTTPSErrors': True,
                    'args': [
                        "--unlimited-storage",
                        "--full-memory-crash-report",
                        "--disable-gpu",
                        "--ignore-certificate-errors",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        # "--force-gpu-mem-available-mb"
                    ],
                    'headless': False})
                return
            except pyppeteer.errors.BrowserError as e:
                logging.warning(e)

    async def reset(self):
        foo = await self.browser.pages()
        self.page = foo[0]
        self.page.setDefaultNavigationTimeout(self.timeout)
        await self.page.emulate({
            'viewport': {
                'width': 360,
                'height': 640,
                'isMobile': True,
                'hasTouch': True,
                'deviceScaleFactor': 3
            },
            'userAgent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3 like Mac OS X) '
            'AppleWebKit/603.1.23 (KHTML, like Gecko) Version/10.0 '
            'Mobile/14E5239e Safari/602.1'
        })

    async def _convert_coordinate(self, x, y, allow_negative=False):
        if allow_negative:
            assert x >= -1 and x <= 1
            assert y >= -1 and y <= 1
        else:
            assert x >= 0 and x <= 1
            assert y >= 0 and y <= 1
        w, h = await self._get_weight_height()
        return w*x, h*y

    async def _get_weight_height(self):
        viewport = await self._send_cmd('Page.getLayoutMetrics', {})
        viewport = viewport['visualViewport']
        return viewport['clientWidth'], viewport['clientHeight']

    async def _send_cmd(self, *args, **kwargs):
        client = self.page._networkManager._client
        return await client.send(*args, **kwargs)

    async def _load_js(self, path, id):
        if id is not None:
            script = await self.page.J(f'#{id}')
            if script:
                return
        await self.page.evaluate(f'''
            var js = document.createElement('script');
            js.setAttribute('src', 'http://localhost:8000/{path}');
            js.setAttribute('id', '{id}');
            document.head.appendChild(js);
        ''')

    async def _enable_scroll(self):
        await self.page.evaluate("""
            document.querySelector('html').setAttribute('style', 'overflow: visible !important;');
            document.querySelector('body').setAttribute('style', 'overflow: visible !important;');
        """, force_expr=True)

    async def _always_open_in_the_same_tab(self):
        await self.page.evaluate("""
        window.open = function (open) {
            return function (url, name, features) {
                name = "_self";
                return open.call(window, url, name, features);
            };
        }(window.open);

        function changeLinkTarget(event){
            if(event.target.closest('a')){
                event.target.closest('a').target = '_self';
            }
        }
        document.addEventListener('click', changeLinkTarget);

        document.querySelectorAll('[target="_blank"]')
            .forEach(x => {x.setAttribute('target', '_self');})
        """, force_expr=True)
        await self._load_js('static/same_tab.js', id='__tracker_same_tab_script')

    async def _enable_segmentation(self):
        await self._load_js('static/seg.js', id='__tracker_seg_script')

    async def _onload(self):
        try:
            await self.page.waitForNavigation(
                waitUntil='domcontentloaded')
        except pyppeteer.errors.TimeoutError:
            await self.page.keyboard.press('Escape')
        await asyncio.gather(
            self._enable_scroll(),
            self._enable_segmentation(),
            self._always_open_in_the_same_tab())

    async def scroll(self, x, y, strength):
        x, y = await self._convert_coordinate(x, y, allow_negative=True)
        return await self._send_cmd(
            'Input.synthesizeScrollGesture',
            {'x': 0, 'y': 0, 'xDistance': 0.1*x*strength, 'yDistance': 0.1*y*strength}
        )

    async def click_at(self, x: float, y: float):
        await self.page.setBypassCSP(True)
        x, y = await self._convert_coordinate(x, y)
        await self.page.touchscreen.tap(x, y)
        await self._onload()

    async def run(self):
        await self.page.setBypassCSP(True)
        await self.page.goto('https://baidu.com')
        await self._onload()
        await self.click_at(0.3, 0.5)
        await self.page.screenshot({'path': f'/tmp/example{self.id}.png'})
        await self.browser.close()

    async def get_segmentation(self):
        i = 0
        while True:
            try:
                return await self._get_segmentation()
            except (pyppeteer.errors.ElementHandleError, pyppeteer.errors.NetworkError) as e:
                if i > 3:
                    raise e
                else:
                    logging.warning(e)
                    await asyncio.sleep(3)

    async def _get_segmentation(self):
        try:
            seg = await self.page.evaluate('recordedElements')
        except pyppeteer.errors.ElementHandleError:
            await self._load_js('static/seg.js', id='__tracker_seg_script')
        await self.page.evaluate(
            "Object.fromEntries = arr => Object.assign({}, ...Array.from(arr, ([k, v]) => ({[k]: v}) ));",
            force_expr=True)
        segmentation = await self.page.evaluate("""
            recordedElements.map(rel => Object.fromEntries(
                Object.entries(rel.elements).map(([k, el]) => {
                    let rect = el.getBoundingClientRect();
                    return [k, {
                        isVisible: el.__tracker_isVisible,
                        x: rect.x,
                        y: rect.y,
                        intersectWidth: el.__tracker_intersectWidth,
                        intersectHeight: el.__tracker_intersectHeight
                    }];
                }
            )))
        """, force_expr=True)
        text = await self.page.evaluate("""
            Object.fromEntries(Object.entries(recordedElements[0].elements)
                .filter(([k, el]) => el.text)
                .map(([k, el]) => [k, el.text])
            )
        """, force_expr=True)
        return segmentation, text

    async def get_state(self):
        segmentation, text = await self.get_segmentation()
        url = self.page.url
        title = await self.page.title()
        img_bytes = await self.page.screenshot()
        ret = {
            'segmentation': segmentation,
            'text': text,
            'url': url,
            'text': text,
            'screenshot': np.array(Image.open(io.BytesIO(img_bytes)).convert('RGB'))
        }
        return ret

    def get_screenshot_from_state(self, state):
        return cv2.resize(state['screenshot'], (360, 640))

    async def press(self, key):
        await self.page.keyboard.press(key)

    async def type(self, word):
        await self.page.keyboard.type(word)

    async def goto(self, url):
        await self.page.setBypassCSP(True)
        try:
            await self.page.goto(url)
        except pyppeteer.errors.TimeoutError:
            await self.page.keyboard.press('Escape')
        await self._onload()

    async def back(self):
        try:
            await self.page.goBack()
        except pyppeteer.errors.TimeoutError:
            await self.page.keyboard.press('Escape')

async def _main(i):
    crawler = await Crawler(i)
    await crawler.run()

async def main():
    await asyncio.gather(_main(0), _main(1))

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(_main(1))