import asyncio
import pyppeteer

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
    async def __init__(self, id):
        self.browser = await pyppeteer.launch(headless=False)
        foo = await self.browser.pages()
        self.page = foo[0]
        self.id = id
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
        for selector in ['html', 'body']:
            el = await self.page.J(selector)
            old_style = await self.page.evaluate("""(el) => {
                el.setAttribute('style', 'overflow: visible !important;')
            }""", el)

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
                waitUntil='domcontentloaded', timeout=5000)
        except pyppeteer.errors.TimeoutError:
            pass
        await asyncio.gather(
            self._enable_scroll(),
            self._enable_segmentation(),
            self._always_open_in_the_same_tab())

    async def scroll(self, x, y):
        x, y = await self._convert_coordinate(x, y, allow_negative=True)
        return self._send_cmd(
            'Input.synthesizeScrollGesture',
            {'x': 0, 'y': 0, 'xDistance': 0.3*x, 'yDistance': 0.3*y}
        )

    async def click_at(self, x: float, y: float):
        x, y = await self._convert_coordinate(x, y)
        await self.page.touchscreen.tap(x, y)
        await self._onload()

    async def run(self):
        await self.page.goto('https://baidu.com')
        await self._onload()
        await self.click_at(0.3, 0.5)
        await self.page.screenshot({'path': f'/tmp/example{self.id}.png'})
        await self.browser.close()

async def _main(i):
    crawler = await Crawler(i)
    await crawler.run()

async def main():
    await asyncio.gather(_main(0), _main(1))

# asyncio.create_task(_main(1))
asyncio.get_event_loop().run_until_complete(_main(1))
