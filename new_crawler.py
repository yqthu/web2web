import asyncio
from pyppeteer import launch

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
        self.browser = await launch()
        self.page = await self.browser.newPage()
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

    async def click_at(self, x: float, y: float):
        x, y = await self._convert_coordinate(x, y)
        client = self.page._networkManager._client
        ret = await self._send_cmd(
            'Input.synthesizeTapGesture', {'x': x, 'y': y}
        )
        return ret

    async def _send_cmd(self, *args, **kwargs):
        client = self.page._networkManager._client
        return await client.send(*args, **kwargs)

    async def run(self):
        await self.page.goto('https://baidu.com')
        await self.click_at(0.3, 0.5)
        await self.page.waitForNavigation({'waitUntil': 'networkidle0'})
        await self.page.screenshot({'path': f'/tmp/example{self.id}.png'})
        await self.browser.close()

async def _main(i):
    crawler = await Crawler(i)
    await crawler.run()

async def main():
    await asyncio.gather(_main(0), _main(1))

asyncio.get_event_loop().run_until_complete(main())
