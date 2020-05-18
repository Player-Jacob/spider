# -*- coding: utf-8 -*-
# @Time         : 2020/5/13 21:01
# @Author       : xiaojiu
# @Project Name : spider
"""
文件名：downloader.py
功能：该模块实现网页下载；
　　　目前实现的功能有：
　　　　　随机切换代理
      支持　content-encoding：　gzip　deflate
      retry
      redirect
"""

import gevent
import gevent.queue
# from gevent import monkey

# monkey.patch_all()
from urllib.parse import urlparse
import json
import time
import copy
import random
import logging
import traceback

import requests

import log
import util
import proxy
import setting


def retry(ExceptionToCheck, tries=2, delay=1, backoff=2):
    """
    下载失败重试装饰器
    :param ExceptionToCheck: 当该异常发生时，重新下载该网页
    :param tries: 最大重试次数
    :param delay: 初始等待重试间隔
    :param backoff: 时间间隔系数，每重试一次，时间间隔乘以该参数
    :return:
    """
    def deco_retry(f):
        def f_retry(self,*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 0:
                try:
                    return f(self, *args, **kwargs)
                except ExceptionToCheck as e:
                    log.logger.exception(e)
                    log.logger.error("{}, Retrying in %d seconds...".format(util.B(str(e)), mdelay))
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
                    lastException = e
                    # 强制更新代理
                    # self.random_set_proxy(request, force=True)
            raise lastException
        return f_retry
    return deco_retry


class ProxyItem:
    """
    代理对象
    """
    def __init__(self, proxy_type=None, host=None, proxy_max_num=10):
        """

        :param proxy_type: 代理类型
        :param host: 代理地址
        :param proxy_max_num: 代理最多连续使用的次数
        """
        self.max_reused_num = setting.PROXY_MAX_NUM if proxy_max_num <= 0 else proxy_max_num
        # 记录当前代理已使用次数
        self.proxy_counter = 0
        self.proxy_type = proxy_type or "http"
        self.host = host

    def get_proxy(self):
        """
        返回该代理类型和主机地址，同时计数器加1
        :return:
        """
        if self.proxy_counter >= self.max_reused_num:
            return None, None

        self.proxy_counter += 1
        return self.proxy_type, self.host

    def is_valid(self):
        return self.proxy_counter < self.max_reused_num

    def __str__(self):
        return "{}:{}".format(self.proxy_type, self.host)


class ProxyManager:
    """
    代理管理
    """
    def __int__(self, proxy_max_num=10, available_proxy=20, proxy_url=None):
        """

        :param proxy_max_num: 代理最多可连续使用次数
        :param available_proxy: 最多可用代理数目
        :param proxy_url:
        :return:
        """
        self.proxy_max_num = setting.PROXY_MAX_NUM if proxy_max_num <= 0 else proxy_max_num
        self.maxsize = setting.PAROXY if available_proxy <= 0 else available_proxy
        self.proxy_url = proxy_url
        self.proxy_queue = gevent.queue.LifoQueue(maxsize=self.maxsize * 5)
        # 代理黑名单， 保存下载失败时使用的代理
        self.black_peoxies = set()

    def random_choice_proxy(self):
        """
        随机从 self.rpoxy_list 中获取一个代理，并将该代理从self.proxy_list删除
        如果 self.proxy_list 元素较少时，重新加载代理
        :return:
        """
        # 重新加载代理
        if len(self.proxy_list) <= 1:
            self.proxy_list = proxy.get_proxy(self.proxy_url)

        # 随机重proxy_list 中获取一个代理，并将该代理从proxy_lsit 中删除
        try:
            index = int(random.random()*len(self.proxy_list))
            proxy_type, host, port = self.proxy_list.pop(index)
        except:
            return  None, None
        else:
            proxy_host = "{}:{}".format(host, port)
            return proxy_type, proxy_host

    def update_black_peoxies(self, host):
        """
        保存所有不可用的代理或者下载超时的代理；每添加一个不可用代理，
        则随机获取一个新的代理放到proxy_queue中
        同时返回新获取的代理
        :param host:
        :return:
        """
        if host:
            self.black_peoxies.add(host)
        return self.random_choice_proxy()

    def init_proxy_queue(self):
        """
        从代理服务器获取代理，初始化代理队列
        :return:
        """
        # 从代理服务器上获取代理
        self.proxy_list = proxy.get_proxy(self.proxy_url)
        if not self.proxy_list:
            return
        for _ in range(self.maxsize):
            proxy_type, proxy_host = self.random_choice_proxy()
            if all([proxy_host, proxy_type]):
                proxy_item = ProxyItem(proxy_type, proxy_host, self.proxy_max_num)
                self.put_proxy(proxy_item)

    def put_proxy(self, proxy_item):
        """
        将代理放入代理队列
        :param proxy_item:
        :return:
        """
        try:
            self.proxy_queue.put(proxy_item, block=False)
        except gevent.queue.Full:
            log.logger.debug("proxy pool is full, discarding proxy: {}".format(proxy_item))

    def get_proxy(self):
        """
        从代理对列中获取一个代理
        判断该代理是否有效；如果有效，将该代理放回对列并返回该代理
        :return:
        """
        proxy_item = None
        try:
            proxy_item = self.proxy_queue.get(False)
        except gevent.queue.Empty as e:
            proxy_type, proxy_host = self.random_choice_proxy()
            return ProxyItem(proxy_type, proxy_host, self.proxy_max_num)
        else:
            if proxy_item.isvalid():
                return proxy_item
            else:
                self.get_proxy()

