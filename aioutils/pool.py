#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Gevent pool/group alike: make asyncio easier to use

Usage::

>>> async def f(url):
...     r = await aiohttp.request('get', url)
...     content = await r.read()
...     print('{}: {}'.format(url, content[:80]))

>>> g = Group()
>>> g.spawn(f('http://www.baidu.com'))
>>> g.spawn(f('http://www.sina.com.cn'))
>>> g.join()

>>> # limit the concurrent coroutines to 3
>>> p = Pool(3)
>>> for _ in range(10):
...     p.spawn(f('http://www.baidu.com'))
>>> p.join()
"""
import asyncio


class Group(object):

    def __init__(self, loop=None):
        try:
            self.loop = loop or asyncio.get_event_loop()
            if self.loop.is_running():
                raise NotImplementedError("Cannot use aioutils in "
                                          "asynchroneous environment")
        except:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self._prepare()

    def _prepare(self):
        self.counter = 0
        self.task_waiter = asyncio.futures.Future(loop=self.loop)

    def spawn(self, coro_or_future):
        self.counter += 1
        task = asyncio.ensure_future(coro_or_future)
        task.add_done_callback(self._on_completion)
        return task

    async_ = spawn

    def _on_completion(self, f):
        self.counter -= 1
        f.remove_done_callback(self._on_completion)
        if self.counter <= 0:
            if not self.task_waiter.done():
                self.task_waiter.set_result(None)

    def join(self):
        def _on_waiter(f):
            self.loop.stop()
            self._prepare()

        self.task_waiter.add_done_callback(_on_waiter)

        # expect the loops to be stop and start multiple times
        while self.counter > 0:
            if not self.loop.is_running():
                self.loop.run_forever()


class Pool(Group):

    def __init__(self, pool_size, loop=None):
        self.sem = asyncio.Semaphore(pool_size, loop=loop)
        super(Pool, self).__init__(loop)

    def spawn(self, coro):
        assert asyncio.iscoroutine(coro), 'pool only accepts coroutine'

        async def _limit_coro():
            async with self.sem:
                return await coro

        self.counter += 1
        task = asyncio.ensure_future(_limit_coro())
        task.add_done_callback(self._on_completion)
        return task

    async_ = spawn
